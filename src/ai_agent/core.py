from __future__ import annotations
import json, os
from typing import Any, Dict, List, Optional
from .types import Hooks, Draft, Decision, Gate, Status, ToolFn
from .utils import mem_write
from .fallbacks import (
    fallback_draft, fallback_decide, fallback_evaluate_critical, fallback_discover_tools
)
from .tools import build_registry_by_names
from .hooks import draft_rule_based, decide_simple, finalize_min

def has(hooks: Hooks, name: str) -> bool: return callable(hooks.get(name))
def try_call(hooks: Hooks, name: str, *args, **kwargs):
    fn = hooks.get(name)
    if not callable(fn): return False, None
    return True, fn(*args, **kwargs)

def log(ctx: Dict[str, Any], event: Dict[str, Any]) -> None:
    ctx.setdefault("events", []).append(event)

def run_cycle(task: str,
              hooks: Hooks | None = None,
              tools: Dict[str, ToolFn] | None = None,
              *,
              catalog: Dict[str, ToolFn] | None = None,
              policy: Optional[Dict[str, Any]] = None,
              max_actions: int = 1) -> Dict[str, Any]:
    hooks = hooks or {}
    tools_active = dict(tools or build_registry_by_names(["calculator"]))  # default
    catalog = dict(catalog or {})
    policy = policy or {"critical_threshold": 0.7, "allow_interrupts": True}
    ctx: Dict[str, Any] = {"task": task, "policy": policy, "events": [], "tools_active": list(tools_active.keys())}

    # recall
    ok, out = try_call(hooks, "recall", task, ctx)
    log(ctx, {"step":"recall","present": ok, "items": len(out or [])})

    # draft
    draft: Draft = hooks["draft"](task, ctx) if has(hooks,"draft") else fallback_draft(task, ctx)
    log(ctx, {"step":"draft","source":"hook" if has(hooks,"draft") else "fallback","draft": draft})

    # decide
    decision: Decision = hooks["decide"](task, draft, ctx) if has(hooks,"decide") else fallback_decide(task, draft, ctx)
    log(ctx, {"step":"decide","source":"hook" if has(hooks,"decide") else "fallback","decision": decision})

    # discover (next cycle only)
    discovered = (hooks["discover_tools"](task, decision, ctx, catalog) if has(hooks,"discover_tools")
                  else fallback_discover_tools(task, decision, ctx, catalog))
    log(ctx, {"step":"discover","candidates": discovered})
    if discovered: mem_write({"type":"tool_proposals","task": task, "candidates": discovered})

    # act
    tool_status: Optional[Status] = None
    tool_output: Optional[Any] = None
    if decision.get("kind")=="use_tool" and max_actions>0:
        tname, targs = decision.get("tool"), decision.get("args", {})
        tool_fn = tools_active.get(tname)
        if callable(tool_fn):
            res = tool_fn(targs, ctx)
            tool_status = res.get("status")
            tool_output = res.get("content") if tool_status=="ok" else res.get("error")
            log(ctx, {"step":"act","tool": tname, "status": tool_status, "output": tool_output, "meta": res.get("meta")})
        else:
            log(ctx, {"step":"act","tool": tname, "status":"skipped", "reason":"tool missing"})

    # reflect
    ok, out = try_call(hooks, "reflect", task=task, draft=draft, decision=decision,
                       tool_status=tool_status, tool_output=tool_output, ctx=ctx)
    revised = out if ok else None
    log(ctx, {"step":"reflect","present": ok, "revised": bool(revised)})

    # gate
    gate: Gate = (hooks["evaluate_critical"](task, draft, decision, tool_status, tool_output, ctx, policy)
                  if has(hooks,"evaluate_critical")
                  else fallback_evaluate_critical(task, draft, decision, tool_status, tool_output, ctx, policy))
    if gate.get("intervene"):
        ok, out = try_call(hooks, "query_user_plan", task=task, gate=gate, ctx=ctx)
        if ok: gate["user_plan"] = out
    log(ctx, {"step":"gate","gate": gate})

    # finalize
    finalizer = hooks["finalize"] if has(hooks,"finalize") else finalize_min
    final_text = finalizer(task=task, draft=draft, decision=decision,
                           tool_status=tool_status, tool_output=tool_output,
                           revised_text=revised, gate=gate, discovered=discovered, ctx=ctx)
    log(ctx, {"step":"finalize","final_text": final_text})

    # persist
    ok, _ = try_call(hooks, "persist", task, ctx, final_text, gate, discovered)
    if not ok:
        mem_write({"task": task, "final": final_text, "gate": gate, "discovered": discovered})
    log(ctx, {"step":"persist","present": ok, "persisted": True})

    return {"final_text": final_text, "used_tool": decision.get("kind")=="use_tool",
            "discovered": discovered, "gate": gate, "trace": ctx.get("events",[])}

# ---- CLI ----
def cli_main():
    import argparse, json
    from .hooks import draft_rule_based, decide_simple, finalize_min
    from .tools import build_registry_by_names
    parser = argparse.ArgumentParser(prog="ai-agent", description="Draft AI Agent")
    parser.add_argument("task", nargs="+", help="task string")
    parser.add_argument("--tools", default="calculator", help="comma list of active tools")
    parser.add_argument("--catalog", default="read_file,write_file,openai_chat", help="comma list of catalog tools")
    parser.add_argument("--critical-threshold", type=float, default=0.7)
    parser.add_argument("--no-interrupts", action="store_true")
    parser.add_argument("--max-actions", type=int, default=1)
    parser.add_argument("--trace", action="store_true")
    args = parser.parse_args()

    task = " ".join(args.task)
    active = [s.strip() for s in args.tools.split(",") if s.strip()]
    cat = [s.strip() for s in args.catalog.split(",") if s.strip()]

    tools_active = build_registry_by_names(active)
    catalog_reg = build_registry_by_names(cat)

    hooks: Hooks = {
        "draft": draft_rule_based,
        "decide": decide_simple,
        "finalize": finalize_min,
    }
    policy = {"critical_threshold": args.critical_threshold,
              "allow_interrupts": not args.no_interrupts}

    result = run_cycle(task, hooks=hooks, tools=tools_active, catalog=catalog_reg,
                       policy=policy, max_actions=args.max_actions)
    print(result["final_text"])
    if args.trace:
        print(json.dumps(result["trace"], indent=2))
