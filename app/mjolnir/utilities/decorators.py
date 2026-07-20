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
                truncated_info = f"\n\n... [Observation truncated at {max_chars} characters (~{max_chars // 4} tokens). To inspect remaining contents, specify narrower query terms or line ranges (start_line/end_line).]"
                result = result[:max_chars] + truncated_info
            return result

        return wrapper

    return decorator
