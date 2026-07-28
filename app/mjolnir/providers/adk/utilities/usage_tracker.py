# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0

import json
import os
from utilities.logger import logger


class UsageTracker:
    """Tracks token usage and transient errors across ADK agents, generating breakdown reports."""

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

        if self.run_dir:
            self.write_to_disk(self.run_dir)

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
        """Extracts and aggregates token usage from an ADK event."""
        if not hasattr(ev, "usage_metadata") or not ev.usage_metadata:
            return

        agent_name = (
            getattr(ev, "author", None)
            or getattr(getattr(ev, "node_info", None), "name", None)
            or "UnknownAgent"
        )

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
        """Writes the usage statistics to a JSON file in the run directory."""
        if run_dir and Path(run_dir).exists():
            usage_data = {
                "total": self.total_usage,
                "errors_grouped": self.error_counts,
                "by_agent": self.usage_by_agent,
            }
            usage_path = Path(run_dir) / "usage.json"
            with open(usage_path, "w") as f:
                json.dump(usage_data, f, indent=2)
            logger.write(f"Token and error usage breakdown saved to {usage_path}")
