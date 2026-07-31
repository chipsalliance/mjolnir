<!-- Licensed under the Apache-2.0 license -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Analysis Providers

Execution backends that scan codebase files and compile findings.

## Directories

- **`mock/`**: Instantly yields hardcoded findings for testing the orchestrator.
- **`genai/`**: Google GenAI SDK (Gemini) backend.
- **`adk/`**: Agent Development Kit (ADK) backend.

## Provider Interface

All providers must implement `run_analysis` in their `main.py`. Refer to the [Mjolnir Application Engine README](../README.md#analysis-providers) for specifications.
