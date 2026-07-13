# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0

import json
import os
import re

from utilities.logger import logger


class UsageTracker:
    """Tracks token usage and transient errors across ADK agents, generating breakdown reports."""

    def __init__(self):
        self.run_dir = None
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

    @staticmethod
    def _parse_proto_text(text: str) -> dict:
        """Structurally tokenizes arbitrary Google Protobuf Text into a Python Dictionary natively."""
        tokens = []
        current = []
        in_str = None
        escape = False

        # 1. Lexical Tokenizer (Handles string bounds so brackets aren't misread)
        for char in text:
            if escape:
                current.append(char)
                escape = False
                continue
            if char == "\\":
                escape = True
                continue

            if in_str:
                if char == in_str:
                    in_str = None
                current.append(char)
            else:
                if char in "\"'":
                    in_str = char
                    current.append(char)
                elif char in " \t\n\r":
                    if current:
                        tokens.append("".join(current))
                        current = []
                elif char in "{}[]":
                    if current:
                        tokens.append("".join(current))
                        current = []
                    tokens.append(char)
                elif char == ":":
                    # Drop colons from token stream as they just imply assignment
                    if current:
                        tokens.append("".join(current))
                        current = []
                else:
                    current.append(char)

        if current:
            tokens.append("".join(current))

        # 2. Recursive Descent Parser
        def parse_block(idx):
            block_dict = {}
            while idx < len(tokens):
                t = tokens[idx]
                if t == "}":
                    return block_dict, idx
                elif t == "]":
                    idx += 1
                    continue

                # Check for block identifier e.g. [namespace.object] {
                if t == "[":
                    tag = []
                    idx += 1
                    while idx < len(tokens) and tokens[idx] != "]":
                        tag.append(tokens[idx])
                        idx += 1
                    block_name = "".join(tag)

                    if idx + 1 < len(tokens) and tokens[idx + 1] == "{":
                        inner, idx = parse_block(idx + 2)
                        block_dict[block_name] = inner
                else:
                    key = t
                    idx += 1
                    if idx < len(tokens):
                        if tokens[idx] == "{":
                            inner, idx = parse_block(idx + 1)
                            block_dict[key] = inner
                        else:
                            val = tokens[idx]
                            if (val.startswith('"') and val.endswith('"')) or (
                                val.startswith("'") and val.endswith("'")
                            ):
                                val = val[1:-1]
                            block_dict[key] = val

                idx += 1
            return block_dict, idx

        parsed, _ = parse_block(0)
        return parsed

    def track_error(self, e: Exception, agent_name: str = "system"):
        """Records an encountered error to surface in the final summary."""
        # Natively unwrap the exception chain down to the base root cause
        root_e = e
        seen = set()
        while root_e and id(root_e) not in seen:
            seen.add(id(root_e))
            if getattr(root_e, "__cause__", None):
                root_e = root_e.__cause__
            elif getattr(root_e, "__context__", None):
                root_e = root_e.__context__
            elif getattr(root_e, "error", None) and isinstance(
                getattr(root_e, "error"), Exception
            ):
                root_e = getattr(root_e, "error")
            else:
                break

        root_err_str = str(root_e)
        root_type = type(root_e).__name__

        clean_err = None

        # Method 1: Google GenAI SDK explicit structured dict parsing ONLY
        if hasattr(root_e, "details") and isinstance(root_e.details, dict):
            err_payload = root_e.details.get("error", {})
            api_code = err_payload.get("code", "UNKNOWN")
            api_status = err_payload.get("status", "UNKNOWN")
            api_reason = ""

            for d in err_payload.get("details", []):
                meta = d.get("metadata", {})
                if "queue_reason" in meta:
                    api_reason = f"-{meta['queue_reason']}"
                    break

                # If Vertex didn't pass a metadata struct but provided a generic error debug payload
                detail_str = d.get("detail", "")

                try:
                    # 1. First traverse structurally for the internal Servo queue reason block:
                    structured_payload = UsageTracker._parse_proto_text(detail_str)

                    if "jax.wiz.servo.ServoErrorDetail" in structured_payload:
                        servo_det = structured_payload["jax.wiz.servo.ServoErrorDetail"]
                        if isinstance(servo_det, list):
                            servo_det = servo_det[0]
                        if "error_code" in servo_det:
                            api_reason = f"-{servo_det['error_code']}"
                            break

                    # 2. Fall back to the Google front-door load-shedding prefix
                    if "::" in detail_str:
                        api_reason = f"-{detail_str.split('::', 1)[1].split(':', 1)[0].split("'")[0].strip()}"
                        break
                except Exception:
                    pass

            if api_code != "UNKNOWN":
                clean_err = f"{api_code}-{api_status}{api_reason}"

        # Method 2: Google API Core gRPC explicit dict parsing ONLY
        if (
            not clean_err
            and hasattr(root_e, "details")
            and isinstance(getattr(root_e, "details"), list)
        ):
            for d in root_e.details:
                if hasattr(d, "metadata") and isinstance(d.metadata, dict):
                    if "queue_reason" in d.metadata:
                        clean_err = f"{root_type}: {d.metadata['queue_reason']}"
                        break

        # Method 3: REST client fallback explicit json payload parsing ONLY
        if (
            not clean_err
            and hasattr(root_e, "response")
            and hasattr(root_e.response, "json")
        ):
            try:
                resp = root_e.response.json()
                if isinstance(resp, dict) and "error" in resp:
                    err_payload = resp["error"]
                    for d in err_payload.get("details", []):
                        if "metadata" in d and "queue_reason" in d["metadata"]:
                            clean_err = f"{root_type}: {d['metadata']['queue_reason']}"
                            break
            except Exception:
                pass

        # Literal String Property Extraction if structured payload fails
        if not clean_err:
            if hasattr(root_e, "message") and root_e.message:
                clean_err = f"{root_type}: {root_e.message}"
            else:
                clean_err = f"{root_type}: {root_err_str}"

        self.total_usage["total_errors"] += 1

        if clean_err not in self.error_counts:
            self.error_counts[clean_err] = 0
        self.error_counts[clean_err] += 1

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

        # Update the model string if it was previously unknown but we found one
        if self.usage_by_agent[agent_name]["model"] == "unknown" and getattr(
            ev, "model_version", None
        ):
            self.usage_by_agent[agent_name]["model"] = ev.model_version

        # Track totals
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
        if run_dir and os.path.exists(run_dir):
            usage_data = {
                "total": self.total_usage,
                "errors_grouped": self.error_counts,
                "by_agent": self.usage_by_agent,
            }
            usage_path = os.path.join(run_dir, "usage.json")
            with open(usage_path, "w") as f:
                json.dump(usage_data, f, indent=2)
            logger.write(f"Token and error usage breakdown saved to {usage_path}")


LIVE_TRACKER = UsageTracker()
