"""Script Agent: turns extracted ad concepts + fresh ICP/pain research +
CrowdWisdomTrading's proprietary data into 3 distinct video ad scripts.

Variants (deliberately different angles, not 3 versions of the same idea):
  1. pain_agitate   - opens on the ICP's specific trading pain, agitates it,
                       then resolves with CrowdWisdomTrading.
  2. proof_data     - leads with a striking proprietary data point/stat as
                       the hook, builds credibility, then the offer.
  3. transformation - before/after narrative arc: ICP's trading life before
                       vs. after using CrowdWisdomTrading.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from src.config import PROPRIETARY_DIR, SCRIPTS_DIR
from src.schemas import AdConceptReport, ProprietaryDataPoint, ResearchFinding, ScriptBundle, VideoScript
from src.tools import llm_client
from src.tools.search_exa import search_recent as exa_search
from src.tools.search_tavily import search_recent as tavily_search

SCRIPT_SYSTEM_TEMPLATE = """You are an award-winning direct-response video ad scriptwriter
who also thinks cinematically — think Hormozi-style hooks shot like a film trailer,
not a talking-head text ad. You are writing for CrowdWisdomTrading
(crowdwisdomtrading.com), a financial data/insights company that helps retail
and semi-pro traders make better decisions.

You are writing the "{variant_label}" variant. {variant_brief}

Hard requirements:
- The visual_hook must describe a concrete, filmable, high-motion opening shot
  that stops a scroll in under 3 seconds. No text-on-screen-only hooks.
- Every scene must specify a real VISUAL (camera/action/setting), not just
  what's being said. This is a movie-style ad, not narrated slides.
- The SUM of every scene's duration_sec must itself add up to 30-60 seconds
  total (e.g. 5-8 scenes of 5-8 seconds each). Add the numbers yourself before
  answering. est_duration_sec must equal that sum exactly — it is not a
  separate creative decision.
- A narrator speaks about 2.6 words per second, so a scene's voiceover must fit
  its duration: a 6-second scene holds at most ~15 words. Count the words in
  each line before you answer. Write tight, punchy ad copy — not paragraphs.
- Ground claims in the provided proprietary data and research; do not invent
  statistics that aren't in the supplied data.
- CTA must point to crowdwisdomtrading.com.
"""

VARIANT_BRIEFS = {
    "pain_agitate": (
        "Open on the ICP's specific, visceral trading pain point (from the ad "
        "concepts/research below), agitate it for a few beats, then pivot hard "
        "into how CrowdWisdomTrading resolves it."
    ),
    "proof_data": (
        "Open the hook on a single striking proprietary data point or stat. "
        "Build credibility through evidence, then land the offer."
    ),
    "transformation": (
        "Tell a before/after transformation arc for the ICP: their trading life "
        "before CrowdWisdomTrading vs. after. Contrast visually, not just verbally."
    ),
}


def _load_proprietary_data() -> list[ProprietaryDataPoint]:
    """Loads any JSON files placed in data/proprietary/ (see README for how to
    populate this from the source Drive files) as a list of {label, value, source}."""
    points: list[ProprietaryDataPoint] = []
    for path in PROPRIETARY_DIR.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            items = payload if isinstance(payload, list) else [payload]
            for item in items:
                points.append(ProprietaryDataPoint(**item))
        except Exception:
            continue
    return points


def _research(pain_point: str, icp: str, days: int = 30) -> list[ResearchFinding]:
    query = f"{icp} {pain_point} trading"
    findings: list[ResearchFinding] = []
    try:
        findings.extend(tavily_search(query, days=days))
    except Exception:
        pass
    try:
        findings.extend(exa_search(query, days=days))
    except Exception:
        pass
    return findings


def _generate_variant(
    variant: str,
    icp: str,
    ad_concepts: AdConceptReport,
    research: list[ResearchFinding],
    proprietary: list[ProprietaryDataPoint],
) -> VideoScript:
    system = SCRIPT_SYSTEM_TEMPLATE.format(
        variant_label=variant, variant_brief=VARIANT_BRIEFS[variant]
    )

    concepts_summary = "\n".join(
        f"- pain: {c.pain_point} | hook: {c.hook_type} | promise: {c.core_promise} | tone: {c.tone}"
        for c in ad_concepts.concepts
    )
    patterns_summary = "\n".join(f"- {p}" for p in ad_concepts.synthesized_patterns)
    research_summary = "\n".join(f"- {f.title} ({f.url}): {f.snippet[:200]}" for f in research[:10])
    data_summary = "\n".join(f"- {d.label}: {d.value} (source: {d.source})" for d in proprietary)

    user = f"""ICP: {icp}

Ad concepts extracted from top-performing competitor/niche ads:
{concepts_summary or '(none found)'}

Cross-ad patterns:
{patterns_summary or '(none found)'}

Recent research on this ICP/pain (last 30 days):
{research_summary or '(none found)'}

CrowdWisdomTrading proprietary data available to cite:
{data_summary or '(none loaded — see data/proprietary/, ground claims in general credibility instead)'}

Write the full script now."""

    script = llm_client.generate_structured(system=system, user=user, schema=VideoScript)
    script.variant = variant  # type: ignore[assignment]
    script.icp = icp
    script.source_ad_concepts = [c.pain_point for c in ad_concepts.concepts]
    script.research_refs = [f.url for f in research]
    script.proprietary_data_used = [d.label for d in proprietary]
    return script


def run(icp: str, ad_concepts: AdConceptReport, pain_point: str | None = None) -> ScriptBundle:
    pain = pain_point or (ad_concepts.concepts[0].pain_point if ad_concepts.concepts else "")
    research = _research(pain, icp)
    proprietary = _load_proprietary_data()

    scripts = [
        _generate_variant(variant, icp, ad_concepts, research, proprietary)
        for variant in ("pain_agitate", "proof_data", "transformation")
    ]

    bundle = ScriptBundle(niche=ad_concepts.niche, generated_at=datetime.now(timezone.utc), scripts=scripts)
    out_path = SCRIPTS_DIR / f"scripts_{_slug(ad_concepts.niche)}.json"
    out_path.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")

    for script in bundle.scripts:
        variant_path = SCRIPTS_DIR / f"script_{script.variant}.json"
        variant_path.write_text(script.model_dump_json(indent=2), encoding="utf-8")

    return bundle


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in text.lower()).strip("_")


if __name__ == "__main__":
    import sys

    from src.config import ADS_DIR

    niche_arg = sys.argv[1] if len(sys.argv) > 1 else "stock trading alerts"
    concepts_path = ADS_DIR / f"ad_concepts_{_slug(niche_arg)}.json"
    concepts = AdConceptReport.model_validate_json(concepts_path.read_text(encoding="utf-8"))
    icp_arg = sys.argv[2] if len(sys.argv) > 2 else "self-directed retail swing trader with a full-time job"
    bundle_out = run(icp_arg, concepts)
    print(json.dumps({"scripts_generated": [s.variant for s in bundle_out.scripts]}, indent=2))
