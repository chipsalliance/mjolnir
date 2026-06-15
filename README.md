# Mjolnir

Mjolnir is an AI-driven security auditing framework designed for open-source Root-of-Trust (RoT) projects.

It leverages AI foundation models and adversarial review pipelines to provide continuous security assurance through periodic, incremental scanning of firmware and RTL.

## Directory Structure

*   **[app/mjolnir/](./app/mjolnir/)**: Core Python application engine, including agent tools, data models, and providers (mock, genai). See [Application README](./app/mjolnir/README.md).
*   **[nix/](./nix/)**: Nix infrastructure for job packaging, auto-discovery, and orchestration. See [Nix README](./nix/README.md).
*   **[projects/](./projects/)**: Supported project definitions and job configurations. See [Projects README](./projects/README.md).
*   **`output/`**: Generated analysis reports, run logs, and HTML dashboards.


## Supported Projects

All project definitions, job configurations, and nix setups are located under [projects/](./projects/). See the [Projects README](./projects/README.md) for more details.

## Getting Started

Mjolnir requires Nix with flakes enabled.

### Running an Audit

To run a predefined project audit runner target, execute `nix run`:

```bash
nix run .#<project-runner-target>
```

#### Examples

- **Run All core tests**:
  ```bash
  nix run .#test-all
  ```
- **Run Caliptra SW Mock E2E Audit**:
  ```bash
  nix run .#caliptra-sw-runner-test
  ```
- **Run OpenTitan ROM Audit**:
  ```bash
  nix run .#opentitan-rom
  ```

## Authentication

Mjolnir supports both Google Cloud Vertex AI and the Gemini Developer API.

### Gemini API Key (Gemini Developer API)

Set the API key in your environment:

```bash
export GEMINI_API_KEY="AIzaSy..."
```

### Vertex AI (Google Cloud Platform)

Set up Application Default Credentials (ADC) and project context:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/credentials.json"
export GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
export GOOGLE_CLOUD_LOCATION="global"
```
