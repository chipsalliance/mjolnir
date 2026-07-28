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
  - `usage_tracker.py`: Real-time telemetry and token accounting across ADK `Event` dispatches.
- **`main.py`**: Entrypoint assembling `Workflow(name="MjolnirAnalysis", edges=[...])` and driving execution via `Runner`.
