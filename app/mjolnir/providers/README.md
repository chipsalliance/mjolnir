<!-- Licensed under the Apache-2.0 license -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Analysis Engines

This directory contains the execution backends for Mjolnir analysis:

- **`adk/`**: The core production analysis engine built on Google's Agent Development Kit (ADK). Orchestrates multi-phase auditing, agent tool calling, and adversarial review.
- **`mock/`**: Deterministic mock engine used exclusively for integration tests and local pipeline verification (`model = "mock"`).
