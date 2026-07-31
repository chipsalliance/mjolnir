<!-- Licensed under the Apache-2.0 license -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Utilities

Support modules managing target retrieval, dashboard generation, and logging.

## Files

- **`command.py`**: Subprocess execution helper.
- **`git.py`**: Manages cloning and checking out specific revisions.
- **`discovery.py`**: Discovers relevant target files to scan.
- **`threat_model.py`**: Reads threat model files.
- **`metadata.py`**: Tracks execution context metrics.
- **`dashboard.py`**: Aggregates scan runs to generate the HTML report pages.
- **`upload.py`**: Handles result packaging and GCS uploads.
- **`decorators.py`**: Common execution decorator routines.
- **`logger.py`**: Structured output logging.
- **`templates/`**: HTML/CSS/JS template blueprints for the dashboard.
