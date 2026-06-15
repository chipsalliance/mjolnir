# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
from google.genai import types
from data.review_finding import ReviewFinding
from providers.genai.agents.base import MjolnirAgent

# Local tool imports
from agent_tools.read_file import read_file
from agent_tools.grep_search import grep_search
from agent_tools.glob_files import glob_files


class ReviewerAgent(MjolnirAgent):
    """Adversarial reviewer agent validating a single finding using workspace search tools."""

    def run(self, finding_json_str: str) -> ReviewFinding:
        response = self.client.models.generate_content(
            model=self.model,
            contents=finding_json_str,
            config=types.GenerateContentConfig(
                system_instruction=self.system_instruction,
                response_mime_type="application/json",
                response_schema=ReviewFinding,
                tools=[read_file, grep_search, glob_files],
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=False,
                    maximum_remote_calls=30,
                ),
                safety_settings=self.safety_settings,
            ),
        )
        return ReviewFinding.model_validate_json(self.get_response_text(response))
