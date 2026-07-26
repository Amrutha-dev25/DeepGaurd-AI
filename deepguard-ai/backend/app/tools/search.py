"""Web search tool — enables Report Agent to search for external references.

Searches the web using the Tavily API if configured.
Search is only used for Distribution Analysis in the Report Agent
and never influences the real/fake verdict.
"""

import json
import logging
from typing import Any

from google.adk.tools import FunctionTool

from app.config import settings

logger = logging.getLogger(__name__)


def search_web(query: str, num_results: int = 5) -> dict[str, Any]:
    """Search the web for information about a media claim or known fakes.

    Args:
        query: The search query (e.g., description of the image, known claims).
        num_results: Number of search results to return (default 5, max 10).

    Returns:
        Dict with 'results' (list of {title, url, snippet}) and 'total_results'.
    """
    results: list[dict[str, str]] = []
    api_key = getattr(settings, "tavily_api_key", "")

    if not api_key:
        return {
            "results": [],
            "total_results": 0,
            "note": "Web search not configured — set TAVILY_API_KEY.",
        }

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        response = client.search(query=query, max_results=min(num_results, 10))
        for item in response.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", ""),
            })
        return {"results": results, "total_results": len(results)}
    except ImportError:
        logger.warning("tavily-py not installed — web search unavailable")
        return {"results": [], "total_results": 0, "note": "tavily-py package not installed."}
    except Exception as e:
        logger.warning("Web search failed: %s", e)
        return {"results": [], "total_results": 0, "error": str(e)}


search_tool = FunctionTool(func=search_web)
