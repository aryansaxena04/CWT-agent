"""Meta Ads Library scraping via Apify.

Meta's Ads Library rarely exposes real impression numbers (the
`impressions_with_index` field is null for the overwhelming majority of
ads), so "best working ad" has no reliable ground-truth metric available
through scraping even though the actor accepts an `impressions_desc` sort
hint. We combine two signals instead: the actor's own sort (a real signal
when Meta does return it) for which ads it returns per search, and
`days_running` (an advertiser keeps an ad live because it's converting) to
rank the merged pool across multiple keyword searches.

Verified against a live run of curious_coder/facebook-ads-library-scraper on
2026-09-09 — see the `urls` input format and the nested `snapshot` object in
_to_ad_record; re-check both if you switch actors.
"""

from __future__ import annotations

import urllib.parse
from datetime import datetime, timezone

from apify_client import ApifyClient

from src.config import settings
from src.schemas import AdRecord

_PERIOD_BUCKETS = [
    (7, "last7d"),
    (14, "last14d"),
    (30, "last30d"),
]


def _period_for_window(window_days: int) -> str:
    for max_days, bucket in _PERIOD_BUCKETS:
        if window_days <= max_days:
            return bucket
    return ""  # "all time" fallback for anything wider than 30 days


def _search_url(keyword: str, country: str) -> str:
    q = urllib.parse.quote(keyword)
    return (
        "https://www.facebook.com/ads/library/?active_status=active&ad_type=all"
        f"&country={country}&q={q}&search_type=keyword_unordered&media_type=all"
    )


def _unix_to_iso(ts: int | None) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _to_ad_record(item: dict) -> AdRecord:
    snapshot = item.get("snapshot") or {}

    media_urls: list[str] = []
    media_type = "unknown"
    if snapshot.get("videos"):
        media_urls = [v.get("video_hd_url") or v.get("video_sd_url") for v in snapshot["videos"] if v]
        media_type = "video"
    elif snapshot.get("cards"):
        media_type = "carousel"
    elif snapshot.get("images"):
        media_urls = [img.get("original_image_url") for img in snapshot["images"] if img]
        media_type = "image"

    start_ts = item.get("start_date")
    end_ts = item.get("end_date")
    now_ts = datetime.now(timezone.utc).timestamp()
    if start_ts:
        end_for_calc = end_ts if end_ts else now_ts
        days_running = max(0, int((end_for_calc - start_ts) / 86400))
    else:
        days_running = 0

    body = snapshot.get("body") or {}
    body_text = body.get("text") if isinstance(body, dict) else (body or "")

    return AdRecord(
        ad_id=str(item.get("ad_archive_id") or ""),
        page_name=item.get("page_name") or snapshot.get("page_name") or "unknown",
        body_text=body_text or "",
        headline=snapshot.get("title") or "",
        cta=snapshot.get("cta_text") or "",
        landing_page=snapshot.get("link_url"),
        days_running=days_running,
        start_date=_unix_to_iso(start_ts),
        platforms=item.get("publisher_platform") or [],
        media_urls=[m for m in media_urls if m],
        media_type=media_type,  # type: ignore[arg-type]
        raw=item,
    )


def search_ads(keyword: str, country: str = "US", window_days: int = 30, max_items: int = 100) -> list[AdRecord]:
    """Search the Meta Ads Library for a keyword and return ads still running
    within the given window, pre-sorted by the actor's impressions signal
    where Meta provides one."""
    settings.require("APIFY_API_TOKEN")
    client = ApifyClient(settings.APIFY_API_TOKEN)

    run_input = {
        "urls": [{"url": _search_url(keyword, country)}],
        "count": max(10, max_items),  # actor requires >= 10 charged results
        "scrapePageAds.period": _period_for_window(window_days),
        "scrapePageAds.activeStatus": "active",
        "scrapePageAds.sortBy": "impressions_desc",
    }
    run = client.actor(settings.APIFY_META_ADS_ACTOR).call(run_input=run_input)
    dataset_id = run.default_dataset_id

    records: list[AdRecord] = []
    for item in client.dataset(dataset_id).iterate_items():
        if "error" in item:
            continue
        records.append(_to_ad_record(item))

    return records


def rank_top_ads(ads: list[AdRecord], top_n: int = 10) -> list[AdRecord]:
    """Rank by days_running (proxy for performance), tie-broken by body length
    (longer-form copy tends to indicate a deliberate, tested angle rather than
    a throwaway placement)."""
    return sorted(ads, key=lambda a: (a.days_running, len(a.body_text)), reverse=True)[:top_n]
