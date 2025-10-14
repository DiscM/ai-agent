from __future__ import annotations
from typing import Any, Dict, List, Optional
from .types import Draft, Decision, Gate, Status

def fallback_draft(task: str, ctx: Dict[str, Any]) -> Draft:
    t = task.lower()
    if "percent of" in t:
        try:
            p = float(t.split("%")[0].split()[-1])/100.0
            b = float(t.split("of")[-1].strip().split()[0])
            return {"intent":"compute","expression": f"{p}*{b}"}
        except Exception:
            pass
    return {"intent":"answer","message":"Short reply ready."}

def fallback_decide(task: str, draft: Draft, ctx: Dict[str, Any]) -> Decision:
    if draft.get("intent")=="compute" and draft.get("expression"):
        return {"kind":"use_tool","tool":"calculator","args":{"expression": draft["expression"]}}
    return {"kind":"answer","text": draft.get("message","OK.")}

def fallback_evaluate_critical(task: str, draft: Draft, decision: Decision,
                               tool_status: Optional[Status],
                               tool_output: Optional[Any],
                               ctx: Dict[str, Any], policy: Dict[str, Any]):
    issues: List[Dict[str, Any]] = []
    if decision.get("kind")=="use_tool" and tool_status is None:
        issues.append({"code":"TOOL_MISSING","detail":decision.get("tool","?"),"severity":0.8})
    if tool_status=="error":
        msg = str(tool_output or "").lower(); sev = 0.9
        if any(k in msg for k in ["quota","limit","rate","429"]): sev = 0.85
        issues.append({"code":"TOOL_ERROR","detail":str(tool_output)[:300],"severity":sev})
    text = str(tool_output or "").lower()
    if any(k in text for k in ["api key","unauthorized","forbidden","auth"]):
        issues.append({"code":"AUTH","detail":"auth problem","severity":0.95})
    if any(k in text for k in ["not found","no such file","file not found","missing"]):
        issues.append({"code":"DATA_MISSING","detail":"resource not found","severity":0.7})
    worst = max([i["severity"] for i in issues], default=0.0)
    thr = float(policy.get("critical_threshold",0.7))
    return {"issues":issues, "severity":worst,
            "intervene": bool(worst>=thr and policy.get("allow_interrupts",True)),
            "reason": "threshold exceeded" if worst>=thr else "no critical issues"}

def fallback_discover_tools(task: str, decision: Decision, ctx: Dict[str, Any],
                            catalog: Dict[str, Any] | None):
    if not catalog: return []
    need = decision.get("tool") if decision.get("kind")=="use_tool" else None
    keys = set([k for k in (need or "").split("_") if k]) | {w for w in task.lower().split() if len(w)>3}
    out: List[Dict[str, Any]] = []
    for name in catalog.keys():
        if any(k in name for k in keys):
            out.append({"name":name,"reason":f"matches: {sorted(keys)[:3]}"})
    return out[:5]
