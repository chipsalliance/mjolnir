<!-- Licensed under the Apache-2.0 license -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Data Models

Pydantic schemas governing data structures throughout the pipeline lifecycle.

## Files

- **`vulnerability.py`**: Parent data structure tracking findings history, overall status, and severity.
- **`audit_finding.py`**: Schema for raw vulnerabilities identified during the audit phase.
- **`review_finding.py`**: Schema for verdicts and justifications generated during the reviewer phase.
- **`historical_finding.py`**: Schema modeling historical scan results.
- **`security_report.py`**: Overall job run execution report schema.
- **`severity.py`**: Severity level enums (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
- **`status.py`**: Scan item status enums (`OPEN`, `CLOSED`, `SKIPPED`).
- **`verdict.py`**: Auditor verification verdict enums (`EXPLOITABLE`, `NOT_EXPLOITABLE`, `FALSE_POSITIVE`).
