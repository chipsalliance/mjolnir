# Integration Tests configurations

Mjolnir internal integration tests and infrastructure mock verifications.

## Components

- **`project.nix`**: Registers mock provider as the default for network-free local testing.
- **`jobs/`**: Test scenario specifications.
  - `mock-smoke.nix`: Basic local mock runner check.
  - `mock-gcs.nix`: Verifies mock output packaging and GCS upload.
  - `genai-gemini.nix`: Performs a minimal live Gemini API request to verify authentication via GenAI provider.
  - `genai-gemini-gcs.nix`: Performs a minimal live Gemini API request and upload test via GenAI provider.
  - `adk-gemini.nix`: Performs a test run using the ADK provider.
  - `adk-gemini-gcs.nix`: Performs a test run and upload using the ADK provider.
  - `adk-gemini-ingest.nix`: Performs a test run from a mock vulnerability report file using the ADK provider.
- **`nix/`**: Nix packaging for test execution.
  - `flake.nix`: Registers test runner packages under the root flake.
