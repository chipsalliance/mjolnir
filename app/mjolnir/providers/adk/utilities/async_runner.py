import asyncio
import time
import random
from typing import Any, Optional
from tqdm import tqdm
from utilities.logger import logger

# ----------------- AIMD CONCURRENCY CONTROLLER -----------------
# Additive Increase / Multiplicative Decrease (TCP Congestion Control)
# Shrinks active connections automatically when Vertex quotas hit.
_MAX_CONCURRENCY = 32.0
_CURRENT_CONCURRENCY_LIMIT = 4.0
_ACTIVE_REQUESTS = 0
_AIMD_LOCK = asyncio.Lock()
_AIMD_COND = asyncio.Condition(_AIMD_LOCK)


async def _acquire_concurrency_slot():
    global _ACTIVE_REQUESTS
    async with _AIMD_COND:
        while _ACTIVE_REQUESTS >= int(_CURRENT_CONCURRENCY_LIMIT):
            await _AIMD_COND.wait()
        _ACTIVE_REQUESTS += 1


async def _release_concurrency_slot(is_quota_hit: bool):
    global _ACTIVE_REQUESTS, _CURRENT_CONCURRENCY_LIMIT
    async with _AIMD_COND:
        _ACTIVE_REQUESTS -= 1

        if not is_quota_hit:
            # Additive Increase (slow, careful growth to probe capacity)
            if _CURRENT_CONCURRENCY_LIMIT < _MAX_CONCURRENCY:
                _CURRENT_CONCURRENCY_LIMIT = min(
                    _MAX_CONCURRENCY, _CURRENT_CONCURRENCY_LIMIT + 0.25
                )
        else:
            # Multiplicative Decrease (rapid shrinking on quota rejection)
            new_limit = max(1.0, _CURRENT_CONCURRENCY_LIMIT * 0.5)
            if int(new_limit) < int(_CURRENT_CONCURRENCY_LIMIT):
                logger.write(
                    f"AIMD Controller: Fast-shrinking concurrency from {int(_CURRENT_CONCURRENCY_LIMIT)} down to {int(new_limit)} due to 429 constraint.",
                    stdout=True,
                )
            _CURRENT_CONCURRENCY_LIMIT = new_limit

        _AIMD_COND.notify_all()


def extract_agent_output(res: Any, expected_schema: Any) -> Any:
    """Safely extracts and validates a Pydantic model instance from an ADK node execution result."""
    if res is None or expected_schema is None:
        return res
    if isinstance(res, expected_schema):
        return res
    if isinstance(res, dict):
        try:
            return expected_schema.model_validate(res)
        except Exception:
            return None
    if isinstance(res, str):
        try:
            return expected_schema.model_validate_json(res)
        except Exception:
            text_val = res.strip()
            if text_val.startswith("```json"):
                text_val = text_val[7:]
            if text_val.startswith("```"):
                text_val = text_val[3:]
            if text_val.endswith("```"):
                text_val = text_val[:-3]
            try:
                return expected_schema.model_validate_json(text_val.strip())
            except Exception:
                return None
    if hasattr(res, "output") and res.output is not None:
        return extract_agent_output(res.output, expected_schema)
    if hasattr(res, "candidates") and res.candidates:
        content = getattr(res.candidates[0], "content", None)
        if content and hasattr(content, "parts") and content.parts:
            for p in content.parts:
                if (
                    not getattr(p, "function_call", None)
                    and getattr(p, "text", None) is not None
                ):
                    parsed = extract_agent_output(p.text, expected_schema)
                    if parsed:
                        return parsed
    if hasattr(res, "parts") and res.parts:
        for p in res.parts:
            if (
                not getattr(p, "function_call", None)
                and getattr(p, "text", None) is not None
            ):
                parsed = extract_agent_output(p.text, expected_schema)
                if parsed:
                    return parsed
    return None


async def run_agent_with_backoff(
    ctx,
    agent,
    node_input: Any,
    run_id: str,
    max_retries: int = 6,
    expected_schema: Any = None,
) -> Any:
    """
    Executes an ADK agent with AIMD Concurrency limits and localized exponential backoff on quota hits.
    """
    attempt = 0
    base_delay = 2.0

    while True:
        # Wait for an open TCP-style concurrency slot (managed by AIMD Controller)
        await _acquire_concurrency_slot()

        try:
            res = await ctx.run_node(
                agent,
                node_input=node_input,
                run_id=run_id,
                use_sub_branch=True,
                override_isolation_scope=run_id,
            )
            # Successful execution Additively Increases concurrency limit
            await _release_concurrency_slot(is_quota_hit=False)
            return (
                extract_agent_output(res, expected_schema) if expected_schema else res
            )
        except Exception as e:
            tracker = ctx.state.get("usage_tracker")
            if tracker:
                tracker.track_error(e, agent.name)

            # Natively traverse to the root base exception
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

            error_str = f"{type(root_e).__name__} {str(root_e)}".lower()
            transient_signals = [
                "429",
                "503",
                "502",
                "500",
                "quota",
                "rate limit",
                "timeout",
                "unavailable",
                "connection",
                "socket",
                "litellm",
                "prefill",
                "resourceexhausted",
                "resource_exhausted",
                "overload",
            ]

            is_quota = any(
                q in error_str
                for q in ["429", "quota", "prefill", "exhausted", "overload"]
            )

            # Immediately release the slot. If a quota hit occurred, it Multiplicatively Decreases limit
            await _release_concurrency_slot(is_quota_hit=is_quota)

            if not any(sig in error_str for sig in transient_signals):
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

            # Wait with exponential backoff on THIS specific task (jittered)
            multiplier = 4.0 if is_quota else 2.0
            delay = base_delay * (multiplier ** (attempt - 1))
            jitter = random.uniform(0.1, 2.0)
            total_sleep = delay + jitter

            logger.write(
                f"Transient/Quota error for {run_id} ({error_str[:30]}...). "
                f"Local backoff for {total_sleep:.1f}s (Attempt {attempt}/{max_retries})",
                stdout=True,
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
                pbar.set_postfix(
                    In=usage_tracker.total_usage.get("total_input_tokens", 0),
                    Out=usage_tracker.total_usage.get("total_output_tokens", 0),
                )
                pbar.update(1)

    tasks = [wrapped_worker(item) for item in items]
    await asyncio.gather(*tasks, return_exceptions=True)
    pbar.close()
    return valid_results, exceptions
