# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0

import asyncio
import random
import re
from typing import Any, Optional
from tqdm import tqdm
from utilities.logger import logger

from providers.adk.utilities.aimd_controller import AIMDConcurrencyController

DEFAULT_MAX_RETRIES = 6
DEFAULT_BASE_DELAY = 2.0
MAX_BACKOFF_DELAY = 60.0  # Cap maximum backoff at 60s
QUOTA_BACKOFF_MULTIPLIER = 4.0
TRANSIENT_BACKOFF_MULTIPLIER = 2.0


def extract_agent_output(res: Any, expected_schema: Any) -> Any:
    """Safely extracts and validates a Pydantic model instance from an ADK node execution result."""
    if res is None or expected_schema is None:
        return res
    if isinstance(res, expected_schema):
        return res
    if isinstance(res, dict):
        try:
            return expected_schema.model_validate(res)
        except Exception as e:
            logger.warning(f"Failed to validate dict output against {expected_schema}: {e}")
            return None

    text_val = (
        getattr(res, "output", None)
        or getattr(res, "text", None)
        or (str(res) if isinstance(res, str) else None)
    )
    if isinstance(text_val, str):
        text_val = text_val.strip()
        if text_val.startswith("```"):
            text_val = re.sub(r"^```(?:json)?\s*|\s*```$", "", text_val, flags=re.DOTALL)
        try:
            return expected_schema.model_validate_json(text_val.strip())
        except Exception as e:
            logger.warning(f"Failed to validate JSON output against {expected_schema}: {e}")
            return None

    return None


async def run_agent_with_backoff(
    ctx,
    agent,
    node_input: Any,
    run_id: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
    expected_schema: Any = None,
    aimd_controller: Optional[AIMDConcurrencyController] = None,
) -> Any:
    """Executes an ADK agent with AIMD Concurrency limits and localized exponential backoff on quota hits."""
    if aimd_controller is None:
        aimd_controller = ctx.state.setdefault("aimd_controller", AIMDConcurrencyController())
    max_concurrency = float(ctx.state["batch_size"])
    attempt = 0
    base_delay = DEFAULT_BASE_DELAY

    while True:
        await aimd_controller.acquire(max_concurrency)

        try:
            res = await ctx.run_node(
                agent,
                node_input=node_input,
                run_id=run_id,
                use_sub_branch=True,
                override_isolation_scope=run_id,
            )
            await aimd_controller.release(is_quota_hit=False, max_concurrency=max_concurrency)
            return extract_agent_output(res, expected_schema) if expected_schema else res
        except Exception as e:
            tracker = ctx.state.get("usage_tracker")
            if tracker:
                tracker.track_error(e, agent.name)

            root_e = getattr(e, "__cause__", None) or getattr(e, "__context__", None) or e
            error_str = f"{type(root_e).__name__} {str(root_e)}".lower()

            is_quota = any(
                q in error_str for q in ["429", "quota", "resourceexhausted", "overload", "prefill"]
            )
            is_transient = is_quota or any(
                sig in error_str
                for sig in ["500", "502", "503", "timeout", "unavailable", "connection"]
            )

            await aimd_controller.release(is_quota_hit=is_quota, max_concurrency=max_concurrency)

            if not is_transient:
                logger.error(
                    f"FATAL: Non-retryable error during execution for {run_id}: {e}",
                    exc_info=True,
                )
                raise e

            attempt += 1
            if attempt >= max_retries:
                logger.error(
                    f"FATAL: Agent execution for {run_id} failed after {max_retries} attempts.",
                    exc_info=True,
                )
                raise e

            multiplier = QUOTA_BACKOFF_MULTIPLIER if is_quota else TRANSIENT_BACKOFF_MULTIPLIER
            delay = min(MAX_BACKOFF_DELAY, base_delay * (multiplier ** (attempt - 1)))
            jitter = random.uniform(0.1, 2.0)
            total_sleep = delay + jitter

            logger.info(
                f"Transient/Quota error for {run_id} ({error_str[:30]}...). "
                f"Local backoff for {total_sleep:.1f}s (Attempt {attempt}/{max_retries})"
            )
            await asyncio.sleep(total_sleep)


async def run_batch_with_concurrency(
    items: list[Any],
    worker_fn: Any,
    concurrency_limit: int,
    desc: str,
    unit: str,
    usage_tracker: Optional[Any] = None,
) -> tuple[list[Any], list[Exception]]:
    """Runs an async worker function across items with bounded concurrency and progress tracking."""
    sem = asyncio.Semaphore(concurrency_limit)
    pbar = tqdm(total=len(items), desc=desc, unit=unit, leave=True)
    exceptions: list[Exception] = []
    valid_results: list[Any] = []

    async def wrapped_worker(item: Any):
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

    tasks = [wrapped_worker(item) for item in items]
    await asyncio.gather(*tasks, return_exceptions=True)
    pbar.close()
    return valid_results, exceptions
