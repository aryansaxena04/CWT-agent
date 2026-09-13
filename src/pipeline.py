"""Standalone end-to-end pipeline runner.

Runs the full Ads Manager -> Script Agent -> Video Agent chain without
requiring the Hermes CLI, so the core deliverable (an actual video) doesn't
depend on Hermes plumbing working on any given machine. Hermes orchestrates
the SAME agent functions through the MCP server in src/mcp_server/server.py
for the kanban-board deliverable.
"""

from __future__ import annotations

import argparse
import json
import sys

from src.agents import ads_manager, script_agent, video_agent


def main() -> None:
    parser = argparse.ArgumentParser(description="CrowdWisdomTrading video ad pipeline")
    parser.add_argument("--niche", default="stock trading alerts")
    parser.add_argument(
        "--keywords",
        nargs="+",
        default=["stock trading alerts", "options trading signals", "day trading platform"],
    )
    parser.add_argument("--icp", default="self-directed retail swing trader with a full-time job")
    parser.add_argument("--window-days", type=int, default=30)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--render-all", action="store_true", help="Render all 3 scripts instead of just the best one")
    parser.add_argument(
        "--stage",
        choices=["ads", "scripts", "video", "all"],
        default="all",
        help="Run a single stage (reads prior stage output from disk) or the full chain.",
    )
    args = parser.parse_args()

    if args.stage in ("ads", "all"):
        print(f"[1/3] Ads Manager: searching {args.keywords!r} in niche {args.niche!r}...")
        ranking, concepts = ads_manager.run(args.niche, args.keywords, window_days=args.window_days, top_n=args.top_n)
        print(f"  -> {len(ranking.top_ads)} top ads, {len(concepts.concepts)} concepts extracted")
        if args.stage == "ads":
            return
    else:
        from src.config import ADS_DIR
        from src.schemas import AdConceptReport

        concepts = AdConceptReport.model_validate_json(
            (ADS_DIR / f"ad_concepts_{ads_manager._slug(args.niche)}.json").read_text(encoding="utf-8")
        )

    if args.stage in ("scripts", "all"):
        print(f"[2/3] Script Agent: writing 3 scripts for ICP {args.icp!r}...")
        bundle = script_agent.run(args.icp, concepts)
        print(f"  -> scripts: {[s.variant for s in bundle.scripts]}")
        if args.stage == "scripts":
            return
    else:
        from src.config import SCRIPTS_DIR
        from src.schemas import ScriptBundle

        bundle = ScriptBundle.model_validate_json(
            (SCRIPTS_DIR / f"scripts_{ads_manager._slug(args.niche)}.json").read_text(encoding="utf-8")
        )

    print("[3/3] Video Agent: rendering...")
    results = video_agent.run(bundle, render_all=args.render_all)
    for r in results:
        status = "OK" if r.success else "FAILED"
        print(f"  -> [{status}] {r.script_variant} ({r.renderer}): {r.output_path or r.notes}")

    if not all(r.success for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
