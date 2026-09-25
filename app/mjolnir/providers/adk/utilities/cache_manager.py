# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0

import os
from typing import Any, List, Optional
from constants import (
    DEFAULT_CONTEXT_CACHE_TTL_SECONDS,
    MIN_CONTEXT_CACHE_CHARS_ESTIMATE,
    MIN_CONTEXT_CACHE_TOKENS,
    SET_MODEL_RESPONSE_INSTRUCTION,
)
from google.adk.tools import FunctionTool
from google.adk.tools.set_model_response_tool import SetModelResponseTool
from google.adk.utils.output_schema_utils import can_use_output_schema_with_tools
from google.genai import Client, types
from utilities.logger import logger


class PhaseContextCache:
    """Manages the lifecycle of an explicit Vertex AI / Gemini context cache for an ADK phase."""

    _instances: dict[str, "PhaseContextCache"] = {}
    _replacements: dict[str, Optional[str]] = {}

    def __init__(
        self,
        model: str,
        instruction: str,
        tools: Optional[List[Any]] = None,
        output_schema: Optional[Any] = None,
        ttl_seconds: int = DEFAULT_CONTEXT_CACHE_TTL_SECONDS,
        display_name: str = "mjolnir-phase-cache",
    ):
        self.model = model
        self.tools = list(tools or [])
        if output_schema and self.tools and not can_use_output_schema_with_tools(model):
            self.tools.append(SetModelResponseTool(output_schema))
            self.instruction = f"{instruction}\n\n{SET_MODEL_RESPONSE_INSTRUCTION}"
        else:
            self.instruction = instruction
        self.ttl_seconds = ttl_seconds
        self.display_name = display_name
        self.cache_name: Optional[str] = None
        self.client: Optional[Client] = None

    def create(self) -> Optional[str]:
        """Creates the cached content object on Vertex AI / Gemini API.

        Returns the cache name (e.g. 'projects/.../cachedContents/...') or None if
        caching is unsupported or failed.
        """
        if not self.model or not self.model.lower().startswith("gemini"):
            return None

        estimated_chars = len(self.instruction) + len(self.tools) * 400
        if estimated_chars < MIN_CONTEXT_CACHE_CHARS_ESTIMATE:
            logger.debug(
                f"Skipping explicit context cache for {self.model}: estimated size "
                f"({estimated_chars} chars) is below minimum threshold "
                f"(~{MIN_CONTEXT_CACHE_TOKENS} tokens)."
            )
            return None

        try:
            vertexai = not bool(os.environ.get("GEMINI_API_KEY"))
            self.client = Client(vertexai=vertexai)

            tools_config = None
            if self.tools:
                func_decls = []
                for t in self.tools:
                    if callable(t) and not isinstance(t, FunctionTool):
                        ft = FunctionTool(t)
                        func_decls.append(ft._get_declaration())
                    elif hasattr(t, "_get_declaration"):
                        func_decls.append(t._get_declaration())
                if func_decls:
                    tools_config = [types.Tool(function_declarations=func_decls)]

            cache_config = types.CreateCachedContentConfig(
                system_instruction=self.instruction,
                tools=tools_config,
                ttl=f"{self.ttl_seconds}s",
                display_name=self.display_name[:128],
            )

            cached_content = self.client.caches.create(
                model=self.model,
                config=cache_config,
            )
            self.cache_name = cached_content.name
            self._instances[self.cache_name] = self
            logger.info(
                f"Created explicit context cache ({cached_content.name}) for {self.model} (TTL={self.ttl_seconds}s)"
            )
            return self.cache_name
        except Exception as e:
            err_str = str(e)
            if "minimum token count" in err_str or "INVALID_ARGUMENT" in err_str:
                logger.debug(f"Explicit context caching skipped (below token threshold): {e}")
            else:
                logger.info(
                    f"Explicit context caching skipped ({e}). Proceeding with standard inference."
                )
            self.cache_name = None
            return None

    def delete(self):
        """Cleans up the cached content object."""
        if self.cache_name and self.client:
            try:
                self.client.caches.delete(name=self.cache_name)
                logger.info(f"Cleaned up context cache {self.cache_name}")
            except Exception as e:
                logger.debug(f"Failed to delete context cache {self.cache_name}: {e}")
            finally:
                self._instances.pop(self.cache_name, None)
                self.cache_name = None

    def __enter__(self):
        self.create()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.delete()
