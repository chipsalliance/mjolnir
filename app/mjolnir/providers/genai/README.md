# GenAI Provider

Production scanning backend leveraging Gemini models.

## Components

- **`main.py`**: Orchestrates the scanning and verification loops.
- **`client.py`**: Resolves credentials and initializes the GenAI SDK client.
- **`agents/`**: Abstractions for distinct AI prompting workflows.
- **`prompts/`**: Base auditor instructions.
- **`threat-models/`**: Domain knowledge threat models injected during scans.
