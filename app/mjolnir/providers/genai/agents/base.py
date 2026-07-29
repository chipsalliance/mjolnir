# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
from google.genai import types
from utilities.logger import logger

IGNORED_BLOCK_REASONS = {
    "None",
    "0",
    "BlockReason.BLOCKED_REASON_UNSPECIFIED",
}

IGNORED_FINISH_REASONS = {
    "STOP",
    "FinishReason.STOP",
    "1",
}


class MjolnirAgent:
    """Base Mjolnir Agent wrapping model context parameters."""

    def __init__(self, client, model: str, system_instruction: str = ""):
        self.client = client
        self.model = model
        self.system_instruction = system_instruction

    @property
    def safety_settings(self) -> list[types.SafetySetting]:
        return [
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
        ]

    def get_response_text(self, response) -> str:
        """Safely extracts text parts from response candidates to bypass SDK non-text warnings."""
        # Check if prompt was blocked
        prompt_feedback = getattr(response, "prompt_feedback", None)
        if prompt_feedback:
            block_reason = getattr(prompt_feedback, "block_reason", None)
            if block_reason and str(block_reason) not in IGNORED_BLOCK_REASONS:
                logger.warning(
                    f" [API Warning] Prompt BLOCKED by safety filter. Reason: {block_reason}"
                )
                if hasattr(prompt_feedback, "safety_ratings") and prompt_feedback.safety_ratings:
                    ratings = [
                        f"{r.category}: {r.probability}" for r in prompt_feedback.safety_ratings
                    ]
                    logger.warning(f" [API Warning] Prompt Safety Ratings: {', '.join(ratings)}")

        if not response.candidates:
            logger.warning(" [API Warning] API response contains zero candidates.")
            return ""

        candidate = response.candidates[0]
        finish_reason = getattr(candidate, "finish_reason", None)

        # If finish reason is not normal completion, log details
        if finish_reason and str(finish_reason) not in IGNORED_FINISH_REASONS:
            logger.warning(f" [API Warning] Model execution unfinished. Reason: {finish_reason}")
            if hasattr(candidate, "safety_ratings") and candidate.safety_ratings:
                ratings = [f"{r.category}: {r.probability}" for r in candidate.safety_ratings]
                logger.warning(f" [API Warning] Candidate Safety Ratings: {', '.join(ratings)}")

        if not candidate.content or not candidate.content.parts:
            return ""

        has_text = any(getattr(part, "text", None) for part in candidate.content.parts)
        has_calls = any(getattr(part, "function_call", None) for part in candidate.content.parts)

        if not has_text and has_calls:
            logger.warning(
                " [API Warning] Model session ended with a tool call request but no text parts. The maximum tool execution calls limit (10) was likely reached!"
            )

        text_parts = []
        for part in candidate.content.parts:
            text = getattr(part, "text", None)
            if text:
                text_parts.append(text)
        return "".join(text_parts)
