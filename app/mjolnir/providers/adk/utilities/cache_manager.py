# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0

import os
from typing import Any, List, Optional
from google.adk.tools import FunctionTool
from google.genai import Client, types
from utilities.logger import logger


class PhaseContextCache:
    """Manages the lifecycle of an explicit Vertex AI / Gemini context cache for an ADK phase."""

    def __init__(
        self,
        model: str,
        instruction: str,
        tools: Optional[List[Any]] = None,
        ttl_seconds: int = 7200,
        display_name: str = "mjolnir-phase-cache",
    ):
        self.model = model
        self.instruction = instruction
        self.tools = tools or []
        self.ttl_seconds = ttl_seconds
        self.display_name = display_name
        self.cache_name: Optional[str] = None
        self.client: Optional[Client] = None

    def create(self) -> Optional[str]:
        """Creates the cached content object on Vertex AI / Gemini API.

        Returns the cache name (e.g. 'projects/.../cachedContents/...') or None if
        caching is unsupported or failed.
        """
        if not self.model or "mock" in self.model.lower():
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
            logger.info(
                f"Created explicit context cache ({cached_content.name}) for {self.model} (TTL={self.ttl_seconds}s)"
            )
            return self.cache_name
        except Exception as e:
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
                self.cache_name = None

    def __enter__(self):
        self.create()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.delete()
