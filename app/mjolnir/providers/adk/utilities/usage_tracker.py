# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0

import json
import os
from pathlib import Path
from utilities.logger import logger


class UsageTracker:
    """Tracks token usage, tool executions, and transient errors across ADK agents, generating breakdown reports."""

    def __init__(self, run_dir: str = None):
        self.run_dir = run_dir
        self.usage_by_agent = {}
        self.error_counts = {}
        self.total_usage = {
            "prompt_tokens": 0,
            "output_tokens": 0,
            "cache_tokens": 0,
            "thoughts_tokens": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
            "total_errors": 0,
        }
        self.tool_usage_by_agent = {}
        self.tool_usage_by_tool = {}
        self.total_tool_usage = {
            "total_calls": 0,
            "total_successes": 0,
            "total_failures": 0,
        }

    def track_tool_call(self, tool_name: str, success: bool, agent_name: str = "AuditorAgent"):
        """Records a tool invocation, success, and failure stat."""
        self.total_tool_usage["total_calls"] += 1
        if success:
            self.total_tool_usage["total_successes"] += 1
        else:
            self.total_tool_usage["total_failures"] += 1

        # Per-tool breakdown
        if tool_name not in self.tool_usage_by_tool:
            self.tool_usage_by_tool[tool_name] = {"calls": 0, "successes": 0, "failures": 0}
        self.tool_usage_by_tool[tool_name]["calls"] += 1
        if success:
            self.tool_usage_by_tool[tool_name]["successes"] += 1
        else:
            self.tool_usage_by_tool[tool_name]["failures"] += 1

        # Per-agent breakdown
        if agent_name not in self.tool_usage_by_agent:
            self.tool_usage_by_agent[agent_name] = {}
        if tool_name not in self.tool_usage_by_agent[agent_name]:
            self.tool_usage_by_agent[agent_name][tool_name] = {
                "calls": 0,
                "successes": 0,
                "failures": 0,
            }
        self.tool_usage_by_agent[agent_name][tool_name]["calls"] += 1
        if success:
            self.tool_usage_by_agent[agent_name][tool_name]["successes"] += 1
        else:
            self.tool_usage_by_agent[agent_name][tool_name]["failures"] += 1

    def track_error(self, e: Exception, agent_name: str = "system"):
        """Records an encountered error to surface in the final summary."""
        root_e = getattr(e, "__cause__", None) or getattr(e, "__context__", None) or e
        root_type = type(root_e).__name__
        code = getattr(root_e, "code", None) or getattr(root_e, "status_code", None) or root_type

        msg = str(root_e).splitlines()[0] if str(root_e) else ""
        clean_err = f"{code}: {msg[:100]}" if msg and msg != str(code) else str(code)

        self.total_usage["total_errors"] += 1
        self.error_counts[clean_err] = self.error_counts.get(clean_err, 0) + 1

        if agent_name not in self.usage_by_agent:
            self.usage_by_agent[agent_name] = self._get_empty_agent_stats()

        self.usage_by_agent[agent_name]["errors"] += 1

    def _get_empty_agent_stats(self):
        return {
            "model": "unknown",
            "prompt_tokens": 0,
            "output_tokens": 0,
            "cache_tokens": 0,
            "thoughts_tokens": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
            "errors": 0,
        }

    def add(self, ev):
        """Extracts and aggregates token and tool usage from an ADK event."""
        agent_name = (
            getattr(ev, "author", None)
            or getattr(getattr(ev, "node_info", None), "name", None)
            or "UnknownAgent"
        )

        # Track tool responses if present in event content
        parts = getattr(getattr(ev, "content", None), "parts", []) or []
        for part in parts:
            fn_res = getattr(part, "function_response", None)
            if fn_res:
                tool_name = getattr(fn_res, "name", "unknown_tool")
                response_content = str(getattr(fn_res, "response", ""))
                success = not any(
                    err_kw in response_content.lower()
                    for err_kw in [
                        "error:",
                        "failed with exception",
                        "timed out",
                        "access denied",
                    ]
                )
                self.track_tool_call(tool_name=tool_name, success=success, agent_name=agent_name)

        if not hasattr(ev, "usage_metadata") or not ev.usage_metadata:
            return

        p_tokens = getattr(ev.usage_metadata, "prompt_token_count", 0) or 0
        o_tokens = getattr(ev.usage_metadata, "candidates_token_count", 0) or 0
        c_tokens = getattr(ev.usage_metadata, "cached_content_token_count", 0) or 0
        t_tokens = getattr(ev.usage_metadata, "thoughts_token_count", 0) or 0

        if agent_name not in self.usage_by_agent:
            self.usage_by_agent[agent_name] = self._get_empty_agent_stats()

        if self.usage_by_agent[agent_name]["model"] == "unknown" and getattr(
            ev, "model_version", None
        ):
            self.usage_by_agent[agent_name]["model"] = ev.model_version

        input_tokens = p_tokens + c_tokens
        output_tokens = o_tokens + t_tokens
        all_tokens = input_tokens + output_tokens

        self.usage_by_agent[agent_name]["prompt_tokens"] += p_tokens
        self.usage_by_agent[agent_name]["output_tokens"] += o_tokens
        self.usage_by_agent[agent_name]["cache_tokens"] += c_tokens
        self.usage_by_agent[agent_name]["thoughts_tokens"] += t_tokens
        self.usage_by_agent[agent_name]["total_input_tokens"] += input_tokens
        self.usage_by_agent[agent_name]["total_output_tokens"] += output_tokens
        self.usage_by_agent[agent_name]["total_tokens"] += all_tokens

        self.total_usage["prompt_tokens"] += p_tokens
        self.total_usage["output_tokens"] += o_tokens
        self.total_usage["cache_tokens"] += c_tokens
        self.total_usage["thoughts_tokens"] += t_tokens
        self.total_usage["total_input_tokens"] += input_tokens
        self.total_usage["total_output_tokens"] += output_tokens
        self.total_usage["total_tokens"] += all_tokens

    def write_to_disk(self, run_dir: str):
        """Writes token_usage.json and tool_usage.json statistics files to disk."""
        if not run_dir or not Path(run_dir).exists():
            return

        token_data = {
            "total": self.total_usage,
            "errors_grouped": self.error_counts,
            "by_agent": self.usage_by_agent,
        }
        token_path = Path(run_dir) / "token_usage.json"
        with open(token_path, "w") as f:
            json.dump(token_data, f, indent=2)
        logger.info(f"Token usage breakdown saved to {token_path}")

        tot_calls = self.total_tool_usage["total_calls"]
        tot_fails = self.total_tool_usage["total_failures"]
        tot_rate = f"{(tot_fails / tot_calls * 100):.2f}%" if tot_calls > 0 else "0.00%"

        by_tool_formatted = {}
        for t_name, stats in self.tool_usage_by_tool.items():
            c = stats["calls"]
            f_count = stats["failures"]
            rate = f"{(f_count / c * 100):.2f}%" if c > 0 else "0.00%"
            by_tool_formatted[t_name] = {**stats, "failure_rate": rate}

        by_agent_formatted = {}
        for a_name, tools in self.tool_usage_by_agent.items():
            by_agent_formatted[a_name] = {}
            for t_name, stats in tools.items():
                c = stats["calls"]
                f_count = stats["failures"]
                rate = f"{(f_count / c * 100):.2f}%" if c > 0 else "0.00%"
                by_agent_formatted[a_name][t_name] = {**stats, "failure_rate": rate}

        tool_data = {
            "total": {
                **self.total_tool_usage,
                "failure_rate": tot_rate,
            },
            "by_tool": by_tool_formatted,
            "by_agent": by_agent_formatted,
        }
        tool_path = Path(run_dir) / "tool_usage.json"
        with open(tool_path, "w") as f:
            json.dump(tool_data, f, indent=2)
        logger.info(f"Tool usage breakdown saved to {tool_path}")
