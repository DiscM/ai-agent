# AI Agent Draft

You provide a task, choose active tools by name, and the agent runs one action per cycle through that pipeline, producing a final answer and a structured trace.
API key goes into tools.py -> requires_env=["OPENAI_API_KEY"]
## Quick start
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .[dev]
ai-agent "calc 19.5% of 349" --tools calculator --trace
```

## Pipeline
`recall → draft → decide → discover → act → reflect → gate → finalize → persist`

- **discover** proposes tools for the next cycle only.
- **gate** evaluates critical issues and may ask for a user plan depending on policy.

## Standardized tool insertion
- **Spec:** `ToolSpec(name, fn, requires_env=[...])`
- **Function signature:** `fn(args: dict, ctx: dict) -> ToolResult`
- **ToolResult:** `{"status":"ok"|"error"|"skipped", "content":..., "error":..., "meta":...}`
- **Registry:** `make_tool_registry([ToolSpec(...)])`
- **Activation:** pass a dict `{name: ToolFn}` to `run_cycle(..., tools=...)`.

### Add a tool
```python
from ai_agent.types import ToolSpec
from ai_agent.tools import make_tool_registry

def tool_fetch_users(args, ctx):
    # your HTTP client here
    return {"status":"error","error":"not wired","meta":{"code":"NOT_WIRED"}}

specs = [ToolSpec(name="fetch_users", fn=tool_fetch_users, requires_env=["MY_API_KEY"])]
tools = make_tool_registry(specs)
```
Set keys via env (`export MY_API_KEY=...`). Missing keys yield a structured error and trigger the gate.

## Hooks (optional)
- `reflect(...) -> Optional[str]`
- Load prior context. If missing: skip.
- `evaluate_critical(...) -> Gate`
- Score issues and set intervene. If missing: fallback evaluator.
- `discover_tools(task, decision, ctx, catalog) -> List[{"name","reason"}]`
- Suggest tools for the next cycle. If missing: fallback suggester.
- `query_user_plan(task, gate, ctx) -> {"allow_continue": bool, ...}`
- Ask user for a plan when intervene is true. If missing: agent returns a prompt instead of blocking.
- `finalize(...) -> str`
- Compose final text. If missing: default finalizer.
- `persist(task, ctx, final_text, gate, discovered) -> Any`
- Save results. If missing: writes JSONL to .agents/memory.jsonl.
- `recall(task, ctx) -> List[Any]`
- Load prior context. If missing: skip.

## Critical gate policy
### Critical threshold

#### Scale guide

* **0.0–0.3** — noise; ignore.
* **0.4–0.6** — minor; log only.
* **0.7–0.84** — high; usually interrupt.
* **0.85–1.0** — critical; interrupt.

#### Built-in triggers and default severities

* **TOOL_MISSING** (decide wants a tool that isn’t active): **0.80**
* **TOOL_ERROR** (generic error): **0.90**
* **RATE_LIMIT** (keywords: `quota`, `limit`, `rate`, `429`): **0.85**
* **AUTH** (keywords: `api key`, `unauthorized`, `forbidden`, `auth`): **0.95**
* **DATA_MISSING** (keywords: `not found`, `no such file`, `file not found`, `missing`): **0.70**

#### Examples

* Missing `read_file` when selected → severity **0.80**. Threshold **0.70** interrupts.
* 401 from API → **0.95**. Always interrupts unless threshold ≥ **0.96**.
* 429 rate limit → **0.85**. Interrupts at **0.70**, not at **0.90+**.
* Bad file path → **0.70**. Interrupts at default **0.70**.

#### Suggested thresholds

* **Interactive dev:** **0.60** to catch issues early.
* **Default:** **0.70**.
* **Unattended batch:** **0.90** to minimize stops.

## Dev
```bash
pytest -q
```

## Notes
- No tool discovery at runtime. Proposals are for the next cycle.
- Natural language cannot install tools. You must register them in code or config.
