# AI Agent – Quick Start

## API key (optional)

If you enable the OpenAI-backed tool, set the key first.

```bash
# mac/linux
export OPENAI_API_KEY=sk-...
# powershell
$env:OPENAI_API_KEY="sk-..."
```

---

## Quick start

```bash
# 1) Create env
python -m venv .venv
# mac/linux
source .venv/bin/activate
# windows
# .\.venv\Scripts\activate

# 2) Install
pip install -e .[dev]
pip install -r requirements.txt   # ensures PyYAML, pytest

# 3) Smoke test (no YAML)
ai-agent "calc 19.5% of 349" --tools calculator --trace

# 4) With YAML config
ai-agent --config config/agent.yaml "calc 10% of 50"

# 5) Run a cog (multi-step)
ai-agent-cog cogs/demo.yaml

# 6) Tests
pytest -q
```

### If the CLI script isn’t found

```bash
python -m ai_agent.core "calc 19.5% of 349" --tools calculator --trace
python -m ai_agent.cog_runner cogs/demo.yaml
```

---

## YAML config

Create `config/agent.yaml`.

```yaml
tools:
  active: [calculator, openai_chat]
  catalog: [read_file, write_file]
policy:
  critical_threshold: 0.7
  allow_interrupts: true
hooks:
  draft: draft_rule_based
  decide: decide_simple
  finalize: finalize_min
```

**Resolution rules**

- Unknown hook/tool names are ignored.
- Env keys are checked at call time; missing keys raise structured errors.
- Merge order: CLI > YAML > code defaults.

---

## Cog runner

Run a sequence of steps defined in YAML.

```bash
ai-agent-cog cogs/demo.yaml
```

**cogs/demo.yaml**** example**

```yaml
agent_config: config/agent.yaml
defaults:
  max_actions: 1
steps:
  - task: "calc 19.5% of 349"
  - task: "calc 10% of 50"
    policy:
      critical_threshold: 0.8
```

---

## Optional hooks

- `recall(task, ctx) -> list`\
  Load prior context. If missing: skip.
- `reflect(task, draft, decision, tool_status, tool_output, ctx) -> str | None`\
  Critique and optionally revise text. If missing: skip.
- `evaluate_critical(task, draft, decision, tool_status, tool_output, ctx, policy) -> Gate`\
  Score issues and set `intervene`. If missing: fallback evaluator.
- `discover_tools(task, decision, ctx, catalog) -> list[{"name","reason"}]`\
  Suggest tools for the next cycle. If missing: fallback suggester.
- `query_user_plan(task, gate, ctx) -> {"allow_continue": bool, ...}`\
  Ask user for a plan when `intervene` is true. If missing: agent returns a prompt instead of blocking.
- `finalize(task, draft, decision, tool_status, tool_output, revised_text, gate, discovered, ctx) -> str`\
  Compose final text. If missing: default finalizer.
- `persist(task, ctx, final_text, gate, discovered) -> Any`\
  Save results. If missing: writes JSONL to `.agents/memory.jsonl`.

**Core hooks (also optional, have fallbacks)**

- `draft(task, ctx) -> Draft`
- `decide(task, draft, ctx) -> Decision`

---

## Critical threshold

### Scale guide

- **0.0–0.3** — noise; ignore.
- **0.4–0.6** — minor; log only.
- **0.7–0.84** — high; usually interrupt.
- **0.85–1.0** — critical; interrupt.

### Built-in triggers and default severities

- **TOOL\_MISSING** (decide wants a tool that isn’t active): **0.80**
- **TOOL\_ERROR** (generic error): **0.90**
- **RATE\_LIMIT** (keywords: `quota`, `limit`, `rate`, `429`): **0.85**
- **AUTH** (keywords: `api key`, `unauthorized`, `forbidden`, `auth`): **0.95**
- **DATA\_MISSING** (keywords: `not found`, `no such file`, `file not found`, `missing`): **0.70**

### Examples

- Missing `read_file` when selected → severity **0.80**. Threshold **0.70** interrupts.
- 401 from API → **0.95**. Always interrupts unless threshold ≥ **0.96**.
- 429 rate limit → **0.85**. Interrupts at **0.70**, not at **0.90+**.
- Bad file path → **0.70**. Interrupts at default **0.70**.

### Suggested thresholds

- **Interactive dev:** **0.60** to catch issues early.
- **Default:** **0.70**.
- **Unattended batch:** **0.90** to minimize stops.

