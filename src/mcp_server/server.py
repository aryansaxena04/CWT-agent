"""MCP server exposing our three agents as tools Hermes can call.

Hermes Agent extends via MCP servers rather than importing Python code
directly, so this is the integration seam between our pipeline and Hermes's
kanban orchestration. Register it with:

    hermes mcp add crowdwisdom python -m src.mcp_server.server

Each tool below wraps the exact same functions the standalone pipeline
(src/pipeline.py) uses, so results are identical whether a run is triggered
through Hermes or directly.
"""

from __future__ import annotations

import json

from mcp.server.mcpserver import MCPServer

from src.agents import ads_manager, script_agent, video_agent
from src.config import ADS_DIR, SCRIPTS_DIR
from src.schemas import AdConceptReport, ScriptBundle

mcp = MCPServer("crowdwisdom-video-ads")


@mcp.tool()
def find_and_analyze_top_ads(niche: str, keywords: list[str], window_days: int = 30, top_n: int = 10) -> str:
    """Search the Meta Ads Library (via Apify) for the given niche/keywords,
    rank the longest-running ads (proxy for 'working'), and extract the
    marketing concepts/pain points/hooks driving them. Saves JSON to
    data/ads/. Returns a JSON summary."""
    ranking, concepts = ads_manager.run(niche, keywords, window_days=window_days, top_n=top_n)
    return json.dumps(
        {
            "niche": niche,
            "top_ads_count": len(ranking.top_ads),
            "top_ads_file": str(ADS_DIR / f"top_ads_{ads_manager._slug(niche)}.json"),
            "concepts_file": str(ADS_DIR / f"ad_concepts_{ads_manager._slug(niche)}.json"),
            "synthesized_patterns": concepts.synthesized_patterns,
        },
        indent=2,
    )


@mcp.tool()
def write_ad_scripts(niche: str, icp: str, pain_point: str = "") -> str:
    """Research the ICP/pain via Tavily+Exa (last 30 days), pull in
    CrowdWisdomTrading proprietary data, and write 3 distinct video ad
    scripts (pain_agitate, proof_data, transformation) as storyboard JSON to
    data/scripts/. Requires find_and_analyze_top_ads to have run first for
    this niche."""
    concepts_path = ADS_DIR / f"ad_concepts_{ads_manager._slug(niche)}.json"
    concepts = AdConceptReport.model_validate_json(concepts_path.read_text(encoding="utf-8"))
    bundle = script_agent.run(icp, concepts, pain_point=pain_point or None)
    return json.dumps(
        {
            "variants_written": [s.variant for s in bundle.scripts],
            "scripts_file": str(SCRIPTS_DIR / f"scripts_{script_agent._slug(niche)}.json"),
        },
        indent=2,
    )


@mcp.tool()
def render_video_ad(niche: str, render_all: bool = False) -> str:
    """Select the strongest of the 3 scripts (or all of them if render_all)
    and render to a 30-60s MP4 via OpenMontage, falling back to the built-in
    FFmpeg renderer if OpenMontage isn't configured locally. Requires
    write_ad_scripts to have run first for this niche."""
    scripts_path = SCRIPTS_DIR / f"scripts_{script_agent._slug(niche)}.json"
    bundle = ScriptBundle.model_validate_json(scripts_path.read_text(encoding="utf-8"))
    results = video_agent.run(bundle, render_all=render_all)
    return json.dumps([r.model_dump() for r in results], indent=2)


if __name__ == "__main__":
    mcp.run()
