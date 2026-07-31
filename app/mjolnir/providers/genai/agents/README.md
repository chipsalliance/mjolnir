<!-- Licensed under the Apache-2.0 license -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# GenAI Agents

Python abstractions for specific AI prompting workflows.

## Files

- **`base.py`**: Wraps model API calls, system instructions, and schema formatting.
- **`auditor.py`**: Specialized agent performing the Phase 1 codebase scan.
- **`adversarial_reviewer.py`**: Specialized agent performing Phase 2 verification to filter false positives.
