# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0

import functools


def limit_tool_output(max_chars=40000):
    """Decorator to truncate tool output if it exceeds max_chars."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            if isinstance(result, str) and len(result) > max_chars:
                truncated_info = f"\n\n... [Warning: Output truncated to {max_chars} chars to save tokens. Please refine your query if you need more data.]"
                return result[:max_chars] + truncated_info
            return result

        return wrapper

    return decorator
