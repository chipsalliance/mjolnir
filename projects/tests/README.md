# Integration Tests configurations

Mjolnir internal integration tests and infrastructure mock verifications.

## Components

- **`project.nix`**: Registers mock provider as the default for network-free local testing.
- **`jobs/`**: Test scenario specifications.
  - `smoke.nix`: Basic local runner check.
  - `gcs.nix`: Verifies mock output packaging and GCS upload.
  - `gemini.nix`: Performs a minimal live Gemini API request to verify authentication.
  - `gemini-gcs.nix`: Performs a minimal live Gemini API request and upload test.
- **`nix/`**: Nix packaging for test execution.
  - `flake.nix`: Registers test runner packages under the root flake.
