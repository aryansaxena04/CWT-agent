"""Exa search wrapper, scoped to recent results for ICP/pain research.

Used as an alternative/complement to Tavily so the Script Agent can
cross-check findings from two independent search backends.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from exa_py import Exa

from src.config import settings
from src.schemas import ResearchFinding


def search_recent(query: str, days: int = 30, max_results: int = 8) -> list[ResearchFinding]:
    settings.require("EXA_API_KEY")
    client = Exa(api_key=settings.EXA_API_KEY)

    start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    response = client.search_and_contents(
        query,
        type="neural",
        num_results=max_results,
        start_published_date=start_date,
        text={"max_characters": 500},
    )

    return [
        ResearchFinding(
            title=r.title or "",
            url=r.url,
            published_date=getattr(r, "published_date", None),
            snippet=(r.text or "")[:500],
        )
        for r in response.results
    ]
