# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0

import asyncio
import re
from typing import Any, Optional

from constants import DEFAULT_DISPATCH_STAGGER_SECONDS
from tqdm import tqdm
from utilities.logger import logger


def extract_agent_text(res: Any, default: str = "") -> str:
    """Extracts plain text output from an ADK node execution result."""
    if res is None:
        return default
    text_val = getattr(res, "output", None) or getattr(res, "text", None) or str(res)
    return str(text_val).strip() if text_val else default


def extract_agent_output(res: Any, expected_schema: Any) -> Any:
    """Safely extracts and validates a Pydantic model instance from an ADK node execution result."""
    if res is None or expected_schema is None or isinstance(res, expected_schema):
        return res
    if isinstance(res, dict):
        try:
            return expected_schema.model_validate(res)
        except Exception as e:
            logger.warning(f"Failed to validate dict output against {expected_schema}: {e}")
            return

    text_val = extract_agent_text(res)
    if text_val:
        if text_val.startswith("```"):
            text_val = re.sub(r"^```(?:json)?\s*|\s*```$", "", text_val, flags=re.DOTALL)
        try:
            return expected_schema.model_validate_json(text_val.strip())
        except Exception as e:
            logger.warning(f"Failed to validate JSON output against {expected_schema}: {e}")


def track_soft_refusal(ctx: Any, result: Any, agent_name: str, target_id: str) -> Optional[str]:
    """Checks a structured agent result for `refusal_reason`, logging and recording it in UsageTracker."""
    refusal_reason = getattr(result, "refusal_reason", None)
    if not refusal_reason:
        return None

    logger.warning(f"{agent_name} soft refusal on '{target_id}': {refusal_reason}")
    tracker = ctx.state.get("usage_tracker")
    if tracker:
        tracker.track_error(
            ValueError(f"SoftRefusal: {refusal_reason}"),
            agent_name,
        )
    return refusal_reason


async def run_agent_node(
    ctx,
    agent,
    node_input: Any,
    run_id: str,
    expected_schema: Any = None,
) -> Any:
    """Executes an ADK agent node with automatic SDK-level retry handling and schema extraction."""
    try:
        res = await ctx.run_node(
            agent,
            node_input=node_input,
            run_id=run_id,
            use_sub_branch=True,
            override_isolation_scope=run_id,
        )
        extracted = extract_agent_output(res, expected_schema) if expected_schema else res
        if expected_schema and extracted is None and res is not None:
            schema_name = getattr(expected_schema, "__name__", str(expected_schema))
            logger.warning(
                f"Agent {agent.name} output failed validation against {schema_name} for {run_id}"
            )
            tracker = ctx.state.get("usage_tracker")
            if tracker:
                tracker.track_error(
                    ValueError(f"SchemaValidationError: {schema_name}"),
                    agent.name,
                )
        elif extracted is not None:
            track_soft_refusal(ctx, extracted, agent.name, run_id)
        return extracted
    except Exception as e:
        tracker = ctx.state.get("usage_tracker")
        if tracker:
            tracker.track_error(e, agent.name)
        logger.error(f"Agent execution failed for {run_id}: {type(e).__name__}: {str(e)[:120]}")


async def run_batch_with_concurrency(
    items: list[Any],
    worker_fn: Any,
    concurrency_limit: int,
    desc: str,
    unit: str,
    usage_tracker: Optional[Any] = None,
    stagger_seconds: float = DEFAULT_DISPATCH_STAGGER_SECONDS,
) -> tuple[list[Any], list[Exception]]:
    """Runs an async worker function across items with bounded concurrency, staggered start, and progress tracking."""
    sem = asyncio.Semaphore(concurrency_limit)
    pbar = tqdm(total=len(items), desc=desc, unit=unit, leave=True)
    exceptions: list[Exception] = []
    valid_results: list[Any] = []

    async def wrapped_worker(idx: int, item: Any):
        if stagger_seconds > 0:
            await asyncio.sleep(min(idx, concurrency_limit) * stagger_seconds)
        async with sem:
            try:
                res = await worker_fn(item)
                if res is not None:
                    valid_results.append(res)
                return res
            except Exception as e:
                exceptions.append(e)
                return e
            finally:
                if (
                    usage_tracker
                    and hasattr(usage_tracker, "total_usage")
                    and isinstance(usage_tracker.total_usage, dict)
                ):
                    pbar.set_postfix(
                        In=usage_tracker.total_usage.get("total_input_tokens", 0),
                        Out=usage_tracker.total_usage.get("total_output_tokens", 0),
                    )
                pbar.update(1)

    tasks = [wrapped_worker(idx, item) for idx, item in enumerate(items)]
    await asyncio.gather(*tasks, return_exceptions=True)
    pbar.close()
    return valid_results, exceptions
