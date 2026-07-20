# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0

# Turn limits (overall LLM round-trip ceilings including synthesis turns)
AUDITOR_MAX_LLM_CALLS = 25
REVIEWER_MAX_LLM_CALLS = 100
INGESTION_MAX_LLM_CALLS = 50

# Tool exploration limits (after which before_tool_callback skips tools and prompts for JSON synthesis)
AUDITOR_MAX_TOOL_CALLS = 20
REVIEWER_MAX_TOOL_CALLS = 90
INGESTION_MAX_TOOL_CALLS = 40
