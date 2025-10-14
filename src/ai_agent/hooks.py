from __future__ import annotations
from typing import Any, Dict, Optional
from .fallbacks import fallback_draft
from .types import Draft, Decision

def draft_rule_based(task: str, ctx: Dict[str, Any]) -> Draft:
    t = task.lower()
    if t.startswith("calc ") or " % of " in t or " percent of " in t:
        t = t.replace("calc ","")
        if "percent of" in t:
            perc = t.split("percent of")[0].strip().rstrip("%"); base = t.split("percent of")[1].strip().split()[0]
        elif "% of" in t:
            perc = t.split("% of")[0].strip(); base = t.split("% of")[1].strip().split()[0]
        else:
            return fallback_draft(task, ctx)
        return {"intent":"compute","expression": f"{float(perc)/100.0}*{float(base)}"}
    return {"intent":"answer","message":"Short reply drafted."}

def decide_simple(task: str, draft: Draft, ctx: Dict[str, Any]) -> Decision:
    if draft.get("intent")=="compute" and draft.get("expression"):
        return {"kind":"use_tool","tool":"calculator","args":{"expression": draft["expression"]}}
    return {"kind":"answer","text": draft.get("message","OK.")}

def finalize_min(**kwargs) -> str:
    gate = kwargs.get("gate") or {}; decision = kwargs.get("decision") or {}
    tool_status = kwargs.get("tool_status"); tool_output = kwargs.get("tool_output")
    revised = kwargs.get("revised_text"); discovered = kwargs.get("discovered") or []
    if gate.get("intervene") and not (gate.get("user_plan") or {}).get("allow_continue", False):
        issues = ", ".join(i["code"] for i in gate.get("issues", [])) or "UNSPECIFIED"
        return f"Action blocked. Provide plan. Issues: {issues}."
    if decision.get("kind")=="use_tool":
        if tool_status=="ok": base = revised or str(tool_output)
        elif tool_status=="error": base = f"tool error: {tool_output}"
        else: base = "skipped action (tool missing)"
    else:
        base = revised or decision.get("text") or "Done."
    if discovered: base += " | Next cycle candidates: " + ", ".join(d["name"] for d in discovered)
    return base

def evaluate_critical_default(task, draft, decision, tool_status, tool_output, ctx, policy):
    from .fallbacks import fallback_evaluate_critical
    res = fallback_evaluate_critical(task, draft, decision, tool_status, tool_output, ctx, policy)
    for i in res["issues"]:
        if i["code"] in {"AUTH","DATA_MISSING"}:
            i["severity"] = max(i["severity"], 0.9)
    res["severity"] = max([i["severity"] for i in res["issues"]], default=0.0)
    res["intervene"] = res["severity"] >= policy.get("critical_threshold", 0.7)
    return res

def query_user_plan_cli(task: str, gate: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    issues = ", ".join(i["code"] for i in gate.get("issues", [])) or "UNSPECIFIED"
    prompt = f"Issues: {issues}. Type 'y' to continue anyway, or paste a short plan: "
    try:
        ans = input(prompt).strip()
        if ans.lower() == "y":
            return {"allow_continue": True, "notes": "user override", "prompt": prompt}
        return {"allow_continue": False, "notes": ans, "prompt": prompt}
    except EOFError:
        return {"allow_continue": False, "notes": None, "prompt": f"Action blocked. Provide plan. {issues}"}
