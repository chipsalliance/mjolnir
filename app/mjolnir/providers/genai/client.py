# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os
from google import genai
from google.genai import types
from utilities.logger import logger


def get_client():
    """Initializes and returns the unified google-genai Client with auto-retries."""
    api_key = os.environ.get("GEMINI_API_KEY")

    http_options = types.HttpOptions(
        retry_options=types.HttpRetryOptions(
            attempts=5,
            initial_delay=2.0,
            max_delay=60.0,
        )
    )

    if api_key:
        logger.success("Using Gemini API Key (with auto-retries)")
        return genai.Client(api_key=api_key, http_options=http_options)

    # Vertex AI mode via ambient ADC
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")

    try:
        client = genai.Client(
            vertexai=True, project=project, location=location, http_options=http_options
        )
        logger.success(
            f"Using Vertex AI (project={client._api_client.project}, location={client._api_client.location}, with auto-retries)"
        )
        return client
    except Exception as e:
        logger.error(f"Failed to initialize Vertex AI client with ADC: {e}")
        return None
