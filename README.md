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
- `draft(task, ctx) -> Draft`
- `decide(task, draft, ctx) -> Decision`
- `reflect(...) -> Optional[str]`
- `evaluate_critical(...) -> Gate`
- `discover_tools(task, decision, ctx, catalog) -> List[{"name","reason"}]`
- `query_user_plan(task, gate, ctx) -> {"allow_continue": bool, ...}`
- `finalize(...) -> str`
- `persist(task, ctx, final_text, gate, discovered) -> Any`
- `recall(task, ctx) -> List[Any]`

## Critical gate policy
- `critical_threshold` is your “slider.” Default `0.7`.
- `allow_interrupts` decides if the agent pauses for a plan.

## Dev
```bash
pytest -q
```

## Notes
- No tool discovery at runtime. Proposals are for the next cycle.
- Natural language cannot install tools. You must register them in code or config.
