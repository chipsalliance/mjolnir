# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""CWE Catalog search agent tool."""

from data.cwe_validator import search_cwe_catalog
from utilities.decorators import limit_tool_output


@limit_tool_output
async def search_cwe(query: str, limit: int = 5) -> str:
    """Searches the bundled official MITRE CWE catalog by keywords to find appropriate CWE IDs.

    Use this tool when you need to identify the exact MITRE CWE identifier and official title
    (e.g., 'CWE-1256', 'CWE-416', 'CWE-208') for a vulnerability.

    Args:
        query: Free-text search terms (e.g. 'hardware interface', 'use after free', 'side channel').
        limit: Maximum number of matching CWE candidates to return (defaults to 5).

    Returns:
        Formatted list of matching CWE IDs, official names, and definitions.
    """
    matches = search_cwe_catalog(query=query, limit=limit)
    if not matches:
        return f"No matching CWEs found in the catalog for query: '{query}'."

    results = []
    for item in matches:
        cwe_id = item.get("id", "")
        name = item.get("name", "")
        desc = item.get("description", "")
        results.append(f"- **{cwe_id}: {name}**\n  {desc}")

    return "\n\n".join(results)
