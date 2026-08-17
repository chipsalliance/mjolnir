<!-- Licensed under the Apache-2.0 license -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Integration Tests configurations

Mjolnir internal integration tests and infrastructure mock verifications.

## Components

- **`project.nix`**: Registers mock provider as the default for network-free local testing.
- **`jobs/`**: Test scenario specifications.
  - `mock-smoke.nix`: Basic local mock runner check.
  - `mock-ci.nix`: PR diff mock runner check.
  - `genai-ci.nix`: PR diff check using GenAI provider.
  - `genai-gemini.nix`: Performs a minimal live Gemini API request to verify authentication via GenAI provider.
  - `adk-ci.nix`: PR diff check using ADK provider.
  - `adk-gemini.nix`: Performs a test run using the ADK provider.
  - `adk-gemini-ingest.nix`: Performs a test run from a mock vulnerability report file using the ADK provider.
- **`nix/`**: Nix packaging for test execution.
  - `flake.nix`: Registers test runner packages under the root flake.
