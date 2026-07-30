# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import asyncio
import functools


def _truncate(result: object, max_chars: int) -> object:
    if isinstance(result, str) and len(result) > max_chars:
        truncated_info = f"\n\n... [Observation truncated at {max_chars} characters (~{max_chars // 4} tokens). To inspect remaining contents, specify narrower query terms or line ranges (start_line/end_line).]"
        return result[:max_chars] + truncated_info
    return result


def limit_tool_output(max_chars=40000):
    """Decorator to truncate tool output if it exceeds max_chars, supporting both sync and async functions."""

    def decorator(func):
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                return _truncate(await func(*args, **kwargs), max_chars)

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                return _truncate(func(*args, **kwargs), max_chars)

            return sync_wrapper

    return decorator
