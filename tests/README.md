<!-- Licensed under the Apache-2.0 license -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Integration Tests

Mjolnir internal integration tests and infrastructure mock verifications.

These targets test Mjolnir's **Python analysis engine, agent workflows, git operations, file discovery, and report generation**. Because these tests evaluate the core orchestration pipeline rather than compiling target firmware, all integration tests run without a compiler development shell (`devShell = null`).

## Components

- **`project.nix`**: Defines the test project and builds the synthetic git fixture repository using `mock_repo.nix`.
- **`mock_repo.nix`**: Nix derivation that constructs a deterministic mock git repository in the Nix store with mock source files, commits, branches, and PR diff history.
- **`jobs/`**: Test scenario specifications:
  - `mock-smoke.nix`: Basic local mock scan verifying discovery, search tools, and report generation (`nix run .#mock-smoke-test`).
  - `mock-ci.nix`: PR diff mode mock verification (`nix run .#mock-ci-test`).
  - `genai-ci.nix`: PR diff check using the GenAI provider (`nix run .#genai-ci-test`).
  - `genai-gemini.nix`: Live Gemini API request verifying ADC/API-key authentication via GenAI provider (`nix run .#genai-gemini-test`).
  - `adk-ci.nix`: PR diff check using the ADK provider graph (`nix run .#adk-ci-test`).
  - `adk-gemini.nix`: Live multi-agent workflow test using the ADK provider (`nix run .#adk-gemini-test`).
  - `adk-gemini-ingest.nix`: Mock report ingestion pipeline test using the ADK provider (`nix run .#adk-gemini-ingest-test`).
  - `ci.nix`: Default CI integration check (`nix run .#ci-test`).
