<!-- Licensed under the Apache-2.0 license -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADK 2.0 Execution Backend (`providers/adk`)

This package implements the core multi-phase security auditing graph using Google's **Agent Development Kit (ADK 2.0)** framework.

## Architecture & Data Flow

The workflow is architected for high scalability using a **unified domain carrier pattern**:

```mermaid
flowchart LR
    P1["Phase 1: Discovery (audit_phase / ingest_report_phase)"] -->|outputs list[Vulnerability]| P2["Phase 2: Adversarial Review (review_phase)"]
    P2 -->|outputs list[Vulnerability]| P3["Phase 3: PoC / Patching (Future phases)"]
    P3 -->|outputs list[Vulnerability]| Main["run_analysis() -> returns clean Vulnerabilities to caller"]
```

- **Canonical Carrier Model**: `Vulnerability` (`data/vulnerability.py`) flows directly across all graph nodes (`list[Vulnerability] -> list[Vulnerability]`).
- **Deterministic State Accumulation**: Each phase worker runs its specialized `Agent` (`AuditorAgent`, `ReviewerAgent`) to generate a phase finding (`AuditFinding`, `ReviewFinding`), then deterministically calls `vuln.add(phase_id, phase_name, finding)` to update live properties (`verdict`, `attack_vector`) and append immutable audit logs (`HistoricalFinding`) to `vuln.history`.

## Directory Structure

- **`phases/`**: Modular definitions of each `@node` stage inside the ADK graph (`Workflow`).
  - `initialize.py`: Seeds session state (`ctx.state`) with execution parameters (`model`, `batch_size`, `code_dir`).
  - `audit.py`: Phase 1 dynamic file scanning across target source paths.
  - `ingest_report.py`: Alternative Phase 1 for processing unstructured security reports or directories (`--ingest`), delegating document reading autonomously to `IngestionAgent` tools.
  - `review.py`: Phase 2 adversarial triaging, evaluating `Status.OPEN` vulnerabilities for exploitability.
- **`agents/`**: Factories returning isolated `Agent` instances (`auditor.py`, `reviewer.py`, `ingestion.py`).
  - `isolated_agent.py`: `IsolatedAgent` wrapper injecting per-invocation cost and turn ceilings without leaking counts to parent workflows.
  - `constants.py`: Pure numeric ceilings for LLM rounds and tool budgets (`AUDITOR_MAX_LLM_CALLS`, `REVIEWER_MAX_TOOL_CALLS`).
- **`utilities/`**: Infrastructure and execution helpers.
  - `async_runner.py`: Provides `run_batch_with_concurrency` (`Semaphore(batch_size)` task bounding) and `run_agent_with_backoff` (AIMD window limiter + localized exponential backoff on `429` quota hits).
  - `cache_manager.py`: Explicit context caching (`PhaseContextCache`) for Gemini models.
  - `usage_tracker.py`: Real-time telemetry and token accounting across ADK `Event` dispatches.
- **`main.py`**: Entrypoint assembling `Workflow(name="MjolnirAnalysis", edges=[...])` and driving execution via `Runner`.

## Supported Models

The `model` field of a job spec selects the foundation model (`model = "mock"` executes the mock testing engine; all other models execute via ADK). ADK resolves models dynamically via its registry:

| Model Prefix            | Engine                     | Auth / Environment                                             | Notes                                                              |
| :---------------------- | :------------------------- | :------------------------------------------------------------- | :----------------------------------------------------------------- |
| `gemini-*`              | Google GenAI / Vertex AI   | `GEMINI_API_KEY` or `gcloud` ADC                               | Default. Supports explicit context caching (`PhaseContextCache`).  |
| `claude-*`              | Claude on Vertex AI        | `gcloud` ADC (`GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`) | Uses ADK's `Claude` integration with Vertex AI.                    |
| `anthropic/claude-*`    | Anthropic via LiteLLM      | `ANTHROPIC_API_KEY`                                            | Calls Anthropic API directly (bypasses Google Cloud / Vertex).     |
| `gpt-*`, `o1-*`, `o3-*` | OpenAI via ADK             | `OPENAI_API_KEY`                                               | Native OpenAI support via ADK's `OpenAILlm`.                       |
| `ollama/<tag>`          | Ollama via LiteLLM         | None (`$OLLAMA_HOST` or default `localhost:11434`)             | Fully local/on-prem inference. Expects model pre-pulled.           |
| `<provider>/<model>`    | 100+ Providers via LiteLLM | Provider-specific API key                                      | LiteLLM passthrough (e.g. `groq/*`, `together_ai/*`, `mistral/*`). |

### Context Caching Behavior

- **Gemini**: `PhaseContextCache` (`utilities/cache_manager.py`) automatically generates explicit Vertex AI cached content objects for system instructions and tool declarations to reduce latency and token usage.
- **Other Providers**: Context caching is safely bypassed (`None` returned), falling back to standard prompt delivery without configuration changes.
