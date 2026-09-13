"""Video Agent: picks the strongest script and renders it to a 30-60s MP4."""

from __future__ import annotations

import json

from src.schemas import ScriptBundle, VideoRenderResult
from src.tools import llm_client
from src.tools.video_render import render_script

SELECTION_SYSTEM = """You are a performance-marketing creative director judging
three video ad scripts for CrowdWisdomTrading. Pick the ONE most likely to
stop a scroll and drive signups, based on hook strength, visual concreteness,
and how well it uses the supplied proof/data. Respond with only the variant
name: pain_agitate, proof_data, or transformation."""


def select_best(bundle: ScriptBundle) -> str:
    if len(bundle.scripts) == 1:
        return bundle.scripts[0].variant

    summaries = "\n\n".join(
        f"[{s.variant}] hook: {s.visual_hook}\nscenes: {len(s.scenes)} | cta: {s.cta}"
        for s in bundle.scripts
    )
    choice = llm_client.chat(SELECTION_SYSTEM, summaries, temperature=0.2).strip().lower()
    valid = {s.variant for s in bundle.scripts}
    return choice if choice in valid else bundle.scripts[0].variant


def run(bundle: ScriptBundle, render_all: bool = False) -> list[VideoRenderResult]:
    if render_all:
        targets = bundle.scripts
    else:
        best_variant = select_best(bundle)
        targets = [s for s in bundle.scripts if s.variant == best_variant]

    return [render_script(script) for script in targets]


if __name__ == "__main__":
    import sys

    from src.config import SCRIPTS_DIR

    niche_arg = sys.argv[1] if len(sys.argv) > 1 else "stock_trading_alerts"
    bundle_path = SCRIPTS_DIR / f"scripts_{niche_arg}.json"
    bundle_in = ScriptBundle.model_validate_json(bundle_path.read_text(encoding="utf-8"))
    render_all_arg = "--all" in sys.argv
    results = run(bundle_in, render_all=render_all_arg)
    print(json.dumps([r.model_dump() for r in results], indent=2))
