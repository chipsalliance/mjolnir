# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0

import json
import os
from pathlib import Path
from typing import Any
from utilities.logger import logger


class UsageTracker:
    """Tracks token usage, tool executions, and transient errors across ADK agents, generating breakdown reports."""

    def __init__(self, run_dir: str = None):
        self.run_dir = run_dir
        self.usage_by_agent = {}
        self.error_counts = {}
        self.total_usage = {
            "prompt_tokens": 0,
            "uncached_tokens": 0,
            "cache_tokens": 0,
            "output_tokens": 0,
            "thoughts_tokens": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
            "total_errors": 0,
        }
        self.tool_usage_by_agent = {}
        self.tool_usage_by_tool = {}
        self.tool_calls_per_item = {}
        self.total_tool_usage = {
            "total_calls": 0,
            "total_successes": 0,
            "total_failures": 0,
        }
        self.reasoning_log = {}

    def track_tool_call(
        self,
        tool_name: str,
        success: bool,
        agent_name: str = "UnknownAgent",
        item_key: str | None = None,
    ):
        """Records a tool invocation, success, failure, and per-item stat."""

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

        # Per-item breakdown
        if item_key:
            if agent_name not in self.tool_calls_per_item:
                self.tool_calls_per_item[agent_name] = {}
            self.tool_calls_per_item[agent_name][item_key] = (
                self.tool_calls_per_item[agent_name].get(item_key, 0) + 1
            )

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
            "uncached_tokens": 0,
            "cache_tokens": 0,
            "output_tokens": 0,
            "thoughts_tokens": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
            "errors": 0,
        }

    def add(self, ev: Any, agent_name: str = "UnknownAgent"):
        """Alias for track_event."""
        return self.track_event(ev, agent_name=agent_name)

    def track_event(self, ev: Any, agent_name: str = "UnknownAgent"):
        """Extracts token usage metadata and function calls/responses from an ADK event."""
        raw_key = getattr(ev, "branch", None)
        if raw_key and "@" in raw_key:
            parts = raw_key.split("@", 1)
            agent_name = getattr(ev, "author", None) or parts[0] or agent_name
            item_key = parts[1]
        else:
            agent_name = getattr(ev, "author", None) or agent_name
            item_key = raw_key

        # Inspect and record thoughts, tool calls, and tool responses
        if hasattr(ev, "content") and ev.content and hasattr(ev.content, "parts"):
            target_key = item_key or agent_name
            if target_key not in self.reasoning_log:
                self.reasoning_log[target_key] = []

            for part in ev.content.parts:
                is_thought = getattr(part, "thought", False)
                text = getattr(part, "text", None)
                fn_call = getattr(part, "function_call", None)
                fn_res = getattr(part, "function_response", None)

                if is_thought and text:
                    self.reasoning_log[target_key].append(
                        {
                            "agent": agent_name,
                            "type": "thought",
                            "content": text.strip(),
                        }
                    )
                elif text and not is_thought:
                    self.reasoning_log[target_key].append(
                        {
                            "agent": agent_name,
                            "type": "output",
                            "content": text.strip(),
                        }
                    )
                elif fn_call:
                    fn_name = getattr(fn_call, "name", "unknown")
                    fn_args = getattr(fn_call, "args", {})
                    serializable_args = fn_args if isinstance(fn_args, dict) else str(fn_args)
                    self.reasoning_log[target_key].append(
                        {
                            "agent": agent_name,
                            "type": "tool_call",
                            "tool": fn_name,
                            "args": serializable_args,
                        }
                    )
                elif fn_res:
                    tool_name = getattr(fn_res, "name", "unknown_tool")
                    resp = getattr(fn_res, "response", "")
                    res_str = resp.get("result", "") if isinstance(resp, dict) else str(resp)
                    clean_str = res_str.strip() if isinstance(res_str, str) else str(res_str)

                    # Tool failure is an explicit tool-level error prefix
                    is_error = clean_str.startswith("Error:")
                    self.track_tool_call(
                        tool_name=tool_name,
                        success=not is_error,
                        agent_name=agent_name,
                        item_key=item_key,
                    )
                    self.reasoning_log[target_key].append(
                        {
                            "agent": agent_name,
                            "type": "tool_response",
                            "tool": tool_name,
                            "response": clean_str[:500] if len(clean_str) > 500 else clean_str,
                        }
                    )

        if not hasattr(ev, "usage_metadata") or not ev.usage_metadata:
            return

        p_tokens = getattr(ev.usage_metadata, "prompt_token_count", 0) or 0
        o_tokens = getattr(ev.usage_metadata, "candidates_token_count", 0) or 0
        c_tokens = getattr(ev.usage_metadata, "cached_content_token_count", 0) or 0
        t_tokens = getattr(ev.usage_metadata, "thoughts_token_count", 0) or 0
        u_tokens = max(0, p_tokens - c_tokens)

        if agent_name not in self.usage_by_agent:
            self.usage_by_agent[agent_name] = self._get_empty_agent_stats()

        if self.usage_by_agent[agent_name]["model"] == "unknown" and getattr(
            ev, "model_version", None
        ):
            self.usage_by_agent[agent_name]["model"] = ev.model_version

        input_tokens = p_tokens
        output_tokens = o_tokens + t_tokens
        all_tokens = input_tokens + output_tokens

        self.usage_by_agent[agent_name]["prompt_tokens"] += p_tokens
        self.usage_by_agent[agent_name]["uncached_tokens"] += u_tokens
        self.usage_by_agent[agent_name]["cache_tokens"] += c_tokens
        self.usage_by_agent[agent_name]["output_tokens"] += o_tokens
        self.usage_by_agent[agent_name]["thoughts_tokens"] += t_tokens
        self.usage_by_agent[agent_name]["total_input_tokens"] += input_tokens
        self.usage_by_agent[agent_name]["total_output_tokens"] += output_tokens
        self.usage_by_agent[agent_name]["total_tokens"] += all_tokens

        self.total_usage["prompt_tokens"] += p_tokens
        self.total_usage["uncached_tokens"] += u_tokens
        self.total_usage["cache_tokens"] += c_tokens
        self.total_usage["output_tokens"] += o_tokens
        self.total_usage["thoughts_tokens"] += t_tokens
        self.total_usage["total_input_tokens"] += input_tokens
        self.total_usage["total_output_tokens"] += output_tokens
        self.total_usage["total_tokens"] += all_tokens

    @staticmethod
    def _calc_stats(counts: list[int]) -> dict[str, Any]:
        """Calculates statistical summary including mean, min, max, p50, and p90."""
        if not counts:
            return {
                "total_items": 0,
                "avg_calls_per_item": 0.0,
                "min": 0,
                "max": 0,
                "p50": 0.0,
                "p90": 0.0,
            }
        s = sorted(counts)
        n = len(s)

        def pct(p: float) -> float:
            k = (n - 1) * (p / 100.0)
            f = int(k)
            c = min(f + 1, n - 1)
            d = k - f
            return round(s[f] + d * (s[c] - s[f]), 2)

        return {
            "total_items": n,
            "avg_calls_per_item": round(sum(s) / n, 2),
            "min": s[0],
            "max": s[-1],
            "p50": pct(50),
            "p90": pct(90),
        }

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
        all_item_counts = []
        for a_name, tools in self.tool_usage_by_agent.items():
            item_counts = list(self.tool_calls_per_item.get(a_name, {}).values())
            all_item_counts.extend(item_counts)
            agent_stats = self._calc_stats(item_counts)

            by_agent_formatted[a_name] = {
                **agent_stats,
                "tools": {},
            }
            for t_name, stats in tools.items():
                c = stats["calls"]
                f_count = stats["failures"]
                rate = f"{(f_count / c * 100):.2f}%" if c > 0 else "0.00%"
                by_agent_formatted[a_name]["tools"][t_name] = {**stats, "failure_rate": rate}

        overall_stats = self._calc_stats(all_item_counts)

        tool_data = {
            "summary": {
                **self.total_tool_usage,
                "failure_rate": tot_rate,
                **overall_stats,
            },
            "by_tool": by_tool_formatted,
            "by_agent": by_agent_formatted,
            "per_item": self.tool_calls_per_item,
        }
        tool_path = Path(run_dir) / "tool_usage.json"
        with open(tool_path, "w") as f:
            json.dump(tool_data, f, indent=2)
        logger.info(f"Tool usage breakdown saved to {tool_path}")

        if self.reasoning_log:
            reasoning_path = Path(run_dir) / "reasoning_log.json"
            with open(reasoning_path, "w") as f:
                json.dump(self.reasoning_log, f, indent=2)
            logger.info(f"Agent reasoning log saved to {reasoning_path}")
