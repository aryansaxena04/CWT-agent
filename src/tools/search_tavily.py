"""Tavily search wrapper, scoped to recent results for ICP/pain research."""

from __future__ import annotations

from tavily import TavilyClient

from src.config import settings
from src.schemas import ResearchFinding


def search_recent(query: str, days: int = 30, max_results: int = 8) -> list[ResearchFinding]:
    settings.require("TAVILY_API_KEY")
    client = TavilyClient(api_key=settings.TAVILY_API_KEY)

    response = client.search(
        query=query,
        search_depth="advanced",
        max_results=max_results,
        days=days,
        include_answer=False,
    )

    return [
        ResearchFinding(
            title=item.get("title", ""),
            url=item.get("url", ""),
            published_date=item.get("published_date"),
            snippet=item.get("content", "")[:500],
        )
        for item in response.get("results", [])
    ]
