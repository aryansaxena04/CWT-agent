"""Ads Manager Agent: finds currently-running ads in the niche via the Meta
Ads Library (through Apify), ranks them, then has an LLM extract the
marketing concepts (pain points, hooks, angles) driving the winners.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from src.config import ADS_DIR
from src.schemas import AdConceptReport, AdRanking
from src.tools import llm_client
from src.tools.apify_ads import rank_top_ads, search_ads

CONCEPT_EXTRACTION_SYSTEM = """You are a senior direct-response marketing strategist.
You will be given a list of ads (page name, body text, headline, CTA, days running)
that have been running the longest in a given niche, which is the public signal
that they are converting. For EACH ad, extract the underlying marketing concept:
the pain point it targets, the hook mechanism it opens with, its core promise,
and its tone. Then separately synthesize 3-6 cross-ad patterns you notice
repeating across the set (recurring pain points, angles, proof types, CTAs).
Be specific and concrete — avoid generic marketing platitudes."""


def run(niche: str, keywords: list[str], window_days: int = 30, top_n: int = 10) -> tuple[AdRanking, AdConceptReport]:
    all_ads = []
    for kw in keywords:
        all_ads.extend(search_ads(kw, window_days=window_days))

    # de-dupe by ad_id across keyword searches
    seen = set()
    unique_ads = []
    for ad in all_ads:
        if ad.ad_id and ad.ad_id not in seen:
            seen.add(ad.ad_id)
            unique_ads.append(ad)

    top_ads = rank_top_ads(unique_ads, top_n=top_n)

    ranking = AdRanking(
        niche=niche,
        keywords=keywords,
        searched_at=datetime.now(timezone.utc),
        window_days=window_days,
        total_ads_found=len(unique_ads),
        top_ads=top_ads,
    )

    ads_path = ADS_DIR / f"top_ads_{_slug(niche)}.json"
    ads_path.write_text(ranking.model_dump_json(indent=2), encoding="utf-8")

    ads_summary = "\n\n".join(
        f"AD {a.ad_id} | page={a.page_name} | days_running={a.days_running} | cta={a.cta}\n"
        f"headline: {a.headline}\nbody: {a.body_text}"
        for a in top_ads
    )
    concept_report = llm_client.generate_structured(
        system=CONCEPT_EXTRACTION_SYSTEM,
        user=f"Niche: {niche}\n\nTop ads:\n\n{ads_summary}",
        schema=AdConceptReport,
    )
    concept_report.niche = niche
    concept_report.generated_at = datetime.now(timezone.utc)

    concepts_path = ADS_DIR / f"ad_concepts_{_slug(niche)}.json"
    concepts_path.write_text(concept_report.model_dump_json(indent=2), encoding="utf-8")

    return ranking, concept_report


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in text.lower()).strip("_")


if __name__ == "__main__":
    import sys

    niche_arg = sys.argv[1] if len(sys.argv) > 1 else "stock trading alerts"
    keyword_args = sys.argv[2:] or ["stock trading alerts", "options trading signals", "day trading platform"]
    ranking_out, concepts_out = run(niche_arg, keyword_args)
    print(json.dumps({"top_ads": len(ranking_out.top_ads), "concepts": len(concepts_out.concepts)}, indent=2))
