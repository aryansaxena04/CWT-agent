# Running this through Hermes Agent

Hermes Agent (NousResearch) is a CLI/config-driven agent, not a Python
library — so this project's actual logic lives in `src/` and is exposed to
Hermes as an **MCP server**. Hermes's orchestrator decomposes the objective
into tasks on its Kanban board; each task calls one of our MCP tools.

The exact profile YAML keys below follow Hermes's documented conventions
(`hermes setup`, `hermes model`, `hermes mcp add`, `hermes profile`) — run
`hermes --help` / `hermes profile --help` on your installed version and
adjust field names if they've changed since these docs were written.

## 1. Install Hermes

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
```

## 2. Point it at OpenRouter

```bash
hermes model openrouter:nvidia/nemotron-3-ultra-550b-a55b:free
hermes config set OPENROUTER_API_KEY <your key>
```

## 3. Register this project's MCP server

Run from the repo root, with `.venv` activated:

```bash
hermes mcp add crowdwisdom -- python -m src.mcp_server.server
```

This exposes three tools to Hermes: `find_and_analyze_top_ads`,
`write_ad_scripts`, `render_video_ad` — the same functions
`src/pipeline.py` calls directly.

## 4. Load the profiles

```bash
hermes profile add hermes/profiles/orchestrator.yaml
hermes profile add hermes/profiles/ads_manager.yaml
hermes profile add hermes/profiles/script_agent.yaml
hermes profile add hermes/profiles/video_agent.yaml
```

## 5. Kick off the objective on the Kanban board

```bash
hermes run --profile orchestrator \
  "Produce a wow cinematic video ad for crowdwisdomtrading.com targeting a \
   self-directed retail swing trader. Search the niche 'stock trading \
   alerts, options trading signals, day trading platform' for the top \
   performing ads over the last 30 days, extract the marketing concepts, \
   write 3 script variants, then render the strongest one."
```

Open the Kanban board (`hermes kanban` or the TUI's board view) to watch the
orchestrator decompose this into tasks across the three profiles and screen-
record that for the submission deliverable.
