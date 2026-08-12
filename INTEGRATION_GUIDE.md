<!-- Licensed under the Apache-2.0 license -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Mjolnir Integration Guide

This guide describes how to integrate Mjolnir into software repositories for automated AI-driven security auditing, continuous PR diff scanning, and centralized artifact export.

---

## Architecture Overview

Mjolnir supports two primary integration patterns:

1. **Continuous PR Security Scanning (GitHub Action)**: Runs on Pull Requests against target repository **X**, restricting analysis to changed text files between the base ref (`base-ref`) and head ref (`head-ref`).
2. **Scheduled / Full Repository Audits (Nix Target)**: Periodically scans the entire repository against repository-specific threat models to generate comprehensive vulnerability reports.

---

## Onboarding Repository X

### Step 1: Register Repository Metadata (`projects/X/project.nix`)

Create a directory under `projects/X/` with a `project.nix` file defining the target repository:

```nix
# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
{
  name = "Repository X Security Audits";
  repoUrl = "https://github.com/org/repo-x.git";
  repoName = "repo-x";
  commit = "main";
  threatModel = "projects/X/threat_model.md";
  srcDirs = [ "src" "firmware" ];
  srcExtensions = [ "rs" "c" "h" "sv" ];
}
```

### Step 2: Define Audit Job Targets (`projects/X/jobs/`)

Create job profile files under `projects/X/jobs/`:

- **`ci.nix` (PR Diff Mode)**:

  ```nix
  {
    name = "repo-x-ci";
    model = "gemini-3.6-flash";
    provider = "adk";
    batchSize = 10;
  }
  ```

- **`main.nix` (Full Audit Mode)**:
  ```nix
  {
    name = "repo-x-full-audit";
    model = "gemini-3.6-flash";
    provider = "adk";
    batchSize = 5;
  }
  ```

### Step 3: Add Threat Model Context

Create a `threat_model.md` file in `projects/X/threat_model.md` detailing:

- High-priority security boundaries (e.g. key management, bootloader, crypto primitives).
- Known attack vectors and threat actors.
- Explicit components out of audit scope.

---

## GitHub Actions Integration (PR Scanning)

To enable automatic PR scanning in repository **X**'s GitHub workflow, add a workflow file `.github/workflows/mjolnir_audit.yml`:

```yaml
name: Mjolnir Security Audit

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  mjolnir-audit:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Run Mjolnir PR Audit
        uses: chipsalliance/mjolnir@main
        with:
          job: "repo-x-ci"
          base-ref: "${{ github.event.pull_request.base.sha }}"
          head-ref: "${{ github.event.pull_request.head.sha }}"
          gcs-bucket: "${{ vars.GCS_REPORTS_BUCKET }}"
```

---

## Environment & Credentials Configuration

### Google Cloud Storage (GCS) Deployment & Sync

To publish audit reports and the interactive web dashboard to a centralized GCS bucket, pass the target bucket via the `--bucket <name>` parameter:

```bash
# Sync local run outputs to GCS
nix run .#deploy-gcs-runs -- --bucket my-gcs-bucket-name

# Deploy the static web dashboard
nix run .#deploy-gcs-web -- --bucket my-gcs-bucket-name
```

Artifacts are hosted in GCS under the following hierarchy:

```text
gs://<bucket-name>/index.html
gs://<bucket-name>/web/...
gs://<bucket-name>/v1/runs/<repo-name>/<job-name>/run_<timestamp>/
```

---

## Export Artifacts & Outputs

For every analysis run, Mjolnir exports structured audit artifacts and compiles them into a centralized **Root Dashboard**:

| Artifact                       | Description                                                                                               |
| :----------------------------- | :-------------------------------------------------------------------------------------------------------- |
| `vulnerabilities.json`         | Complete audit graph containing all discovered vulnerabilities, historical findings, and agent reasoning. |
| `vulnerabilities_minimal.json` | Filtered subset containing only active, verified `Status.OPEN` vulnerabilities.                           |
| `metadata.json`                | Run metadata including execution timestamp, commit SHA, model, provider, and status.                      |
| `job.log`                      | Raw execution log and turn telemetry.                                                                     |
| `dashboard/`                   | Compiled interactive Multi-Page Application (MPA) HTML dashboard bundle.                                  |

### Root Dashboard & Multi-Project Aggregation

Mjolnir compiles all local and published audit runs into a unified **Root Dashboard** (`dashboard.html`):

- **Global Security Overview:** Provides high-level metrics across all integrated repositories (vulnerability counts, severity distributions, and cross-component Sankey flow diagrams).
- **Project Summaries:** Dedicated landing pages for each integrated repository (`project_<repo_name>.html`) summarizing active security posture and historical audit runs.
- **Interactive Run Inspector:** Detailed per-run inspector (`run_<id>.html`) displaying step-by-step agent histories, code context, and recommended remediation patches.
- **Dashboard Compilation:** The root dashboard can be regenerated at any time from existing runs using `nix run .#gen-dashboard`.

---

## Local Verification & Testing

Before deploying to CI, test the integration locally:

```bash
# Verify PR diff scanning mode locally
nix run .#repo-x-ci -- --diff-base HEAD~1 --diff-head HEAD

# Verify full audit mode locally
nix run .#repo-x-full-audit
```
