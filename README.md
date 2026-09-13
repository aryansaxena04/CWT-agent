# CrowdWisdomTrading Video Ads Agent

A multi-agent pipeline that researches winning ads in CrowdWisdomTrading's
niche, writes cinematic video-ad scripts grounded in that research plus
proprietary trading data, and renders a 30-60 second MP4 ad — orchestrated
through [Hermes Agent](https://github.com/nousresearch/hermes-agent)'s
Kanban board.

## Architecture

```
Ads Manager Agent  --(Apify: Meta Ads Library)-->  top_ads.json
                   --(LLM via OpenRouter)-------->  ad_concepts.json
                                |
                                v
Script Agent       --(Tavily + Exa, 30d window)-->  research
                   --(data/proprietary/*.json)---->  proprietary data
                   --(LLM via OpenRouter)-------->  3x script_<variant>.json
                                |
                                v
Video Agent         --(OpenMontage, or fallback)-->  output/videos/ad_*.mp4
```

- **Agent logic**: `src/agents/` (pure Python, no Hermes dependency)
- **Tool wrappers**: `src/tools/` (Apify, Tavily, Exa, OpenRouter, video render)
- **Data contracts**: `src/schemas.py` (pydantic — this is what makes every
  JSON output "human readable" per the assignment spec)
- **Standalone runner**: `src/pipeline.py` — runs the full chain without
  Hermes at all
- **Hermes integration**: `src/mcp_server/server.py` exposes the same three
  agent calls as MCP tools; `hermes/profiles/*.yaml` define the
  orchestrator + 3 sub-agent profiles that run on Hermes's Kanban board. See
  [`hermes/README.md`](hermes/README.md) for exact commands.

Why both a standalone runner *and* Hermes wiring: Hermes is a CLI/config
tool, not a Python framework you import, so the actual pipeline logic has to
exist independently of it either way. The standalone path guarantees the
core deliverable (a real video) doesn't depend on Hermes's plumbing working
on whatever machine re-runs this; the MCP layer is what puts the same logic
on Hermes's Kanban board for the required screen recording.

## Sample output

A real run of the pipeline (niche: "stock trading alerts") is checked in under
[`examples/`](examples/):

| File | What it is |
|---|---|
| `top_ads_stock_trading_alerts.json` | Ads pulled from the Meta Ads Library via Apify, ranked |
| `ad_concepts_stock_trading_alerts.json` | Pain points, hooks and cross-ad patterns extracted from them |
| `script_pain_agitate.json` / `script_proof_data.json` / `script_transformation.json` | The three storyboard scripts |
| `ad_transformation.mp4` | The rendered ad (strongest script, picked by the Video Agent) |

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate        # .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env          # fill in the keys below
```

Required keys (all have free tiers):

| Key | Where to get it |
|---|---|
| `OPENROUTER_API_KEY` | https://openrouter.ai |
| `APIFY_API_TOKEN` | https://apify.com |
| `TAVILY_API_KEY` | https://www.tavily.com |
| `EXA_API_KEY` | https://exa.ai |
| `PEXELS_API_KEY` | https://pexels.com/api (only needed for the fallback video renderer) |

Optional: `OPENMONTAGE_PATH` pointing at a local clone of
[calesthio/OpenMontage](https://github.com/calesthio/OpenMontage) to use it
instead of the built-in fallback renderer. Voiceover uses Microsoft Edge's
free neural voices (no key needed); change `TTS_VOICE` in `.env` to pick a
different one — `python -m src.tools.list_voices` lists them.

### Proprietary data

Download CrowdWisdomTrading's sample datasets from the assignment's Drive
links and drop them as JSON files into `data/proprietary/`, one file per
dataset (or a JSON array of objects), each shaped like:

```json
{ "label": "Avg. win-rate lift after 30 days", "value": "+18%", "source": "<dataset name>" }
```

The Script Agent loads every `*.json` in that folder and grounds script
claims in whatever it finds there.

## Running it

Full pipeline, standalone (no Hermes needed):

```bash
python -m src.pipeline \
  --niche "stock trading alerts" \
  --keywords "stock trading alerts" "options trading signals" "day trading platform" \
  --icp "self-directed retail swing trader with a full-time job"
```

Run a single stage (reads the prior stage's saved JSON):

```bash
python -m src.pipeline --stage ads    --niche "stock trading alerts"
python -m src.pipeline --stage scripts --niche "stock trading alerts"
python -m src.pipeline --stage video   --niche "stock trading alerts" --render-all
```

Through Hermes (produces the Kanban board deliverable): see
[`hermes/README.md`](hermes/README.md).

## Tests

```bash
pytest tests/ -v
```

Covers the pure-logic pieces (ad ranking, schema round-tripping) that don't
require live API keys. The agent functions themselves are integration code
against Apify/Tavily/Exa/OpenRouter/Pexels and are exercised by actually
running the pipeline, not by mocked unit tests.

## Known limitations / design notes

- **"Best working ad" proxy**: Meta's Ads Library doesn't expose spend or
  conversion data for most ad categories. Ranking uses `days_running`
  (an advertiser keeps a losing ad off, not on) as the standard public proxy
  for performance, tie-broken by copy length as a signal of a deliberately
  tested angle vs. a throwaway placement. See `src/tools/apify_ads.py`.
- **OpenMontage integration**: OpenMontage is itself agent-orchestrated
  (YAML manifests + a Python tool registry meant to be driven by a coding
  assistant), not a stable public API. `src/tools/video_render.py` adapts
  our script schema to OpenMontage's documented manifest conventions, but
  the exact keys should be re-checked against a live `OPENMONTAGE_PATH`
  checkout's `pipeline_defs/` before relying on it end-to-end. If unset, the
  pipeline automatically uses the built-in fallback renderer (Pexels stock +
  Edge neural TTS voiceover + MoviePy), which is fully self-contained and does not
  require OpenMontage at all.
- **API keys in this submission**: per the assignment's request to include
  working Apify/Tavily tokens so the reviewer can re-run this without
  burning their own paid accounts, freshly-created free-tier keys dedicated
  to this submission are included in the submission email (not committed to
  this repo, and not reused personal keys) — revoke on request after review.
