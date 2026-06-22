# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os
from google.genai import types
from utilities.logger import logger
from data.security_report import SecurityReport
from providers.genai.agents.base import MjolnirAgent

EXTENSION_TO_PROMPT = {
    "c": "c_auditor.txt",
    "h": "c_auditor.txt",
    "cpp": "c_auditor.txt",
    "cc": "c_auditor.txt",
    "rs": "rust_auditor.txt",
}
DEFAULT_PROMPT = "c_auditor.txt"


class AuditorAgent(MjolnirAgent):
    """Dynamic auditor agent that resolves language prompts and audits code files."""

    def __init__(self, client, model: str, threat_model_context: str = ""):
        super().__init__(client, model)
        self.threat_model_context = threat_model_context

    def _resolve_instruction(self, file_path: str) -> str:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        prompts_dir = os.path.join(current_dir, "..", "prompts")

        ext = os.path.splitext(file_path)[1].lstrip(".").lower()
        if ext not in EXTENSION_TO_PROMPT:
            logger.write(
                f" [API Warning] Unsupported file extension: .{ext}. Defaulting to C auditor.",
                stdout=True,
            )
            prompt_name = DEFAULT_PROMPT
        else:
            prompt_name = EXTENSION_TO_PROMPT[ext]

        p_path = os.path.join(prompts_dir, prompt_name)
        if os.path.exists(p_path):
            with open(p_path, "r", encoding="utf-8") as f:
                base_prompt = f.read().strip()
                logger.write(
                    f"[Prompt Loader] Loaded prompt for .{ext} from: {prompt_name}",
                    stdout=False,
                    indent=2,
                )
                return base_prompt + self.threat_model_context
        return (
            "Analyze this file for potential security vulnerabilities."
            + self.threat_model_context
        )

    def run(self, file_rel_path: str, contents: str) -> SecurityReport:
        logger.write(f"Scanning {file_rel_path} (GenAI)...", stdout=False)
        system_instruction = self._resolve_instruction(file_rel_path)
        file_prompt = (
            f"Analyze this file:\n\nFilename: {file_rel_path}\n\nContent:\n{contents}"
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=file_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=SecurityReport,
                safety_settings=self.safety_settings,
            ),
        )
        return SecurityReport.model_validate_json(self.get_response_text(response))
