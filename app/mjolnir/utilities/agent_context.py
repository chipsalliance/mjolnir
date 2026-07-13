# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import contextvars

# ContextVar holding the current active InvocationContext during agent execution
CURRENT_AGENT_RUN = contextvars.ContextVar("CURRENT_AGENT_RUN", default=None)
CURRENT_RUN_ID = contextvars.ContextVar("CURRENT_RUN_ID", default="")
