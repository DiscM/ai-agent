from __future__ import annotations
import ast, operator as op, os
from typing import Any, Dict, List, Tuple
from .types import ToolSpec, ToolFn, ToolResult

# ---- env handling + registry ----
def _load_env(keys: List[str]) -> Tuple[Dict[str, str], List[str]]:
    found, missing = {}, []
    for k in keys:
        v = os.getenv(k, "")
        if v:
            found[k] = v
        else:
            missing.append(k)
    return found, missing

def make_tool_registry(specs: List[ToolSpec]) -> Dict[str, ToolFn]:
    registry: Dict[str, ToolFn] = {}
    for spec in specs:
        base_fn = spec.fn
        def _wrap(base=base_fn, tool_name=spec.name, needs=spec.requires_env):
            def wrapped(args: Dict[str, Any], ctx: Dict[str, Any]) -> ToolResult:
                secrets, missing = _load_env(needs)
                if missing:
                    return {"status": "error", "error": f"missing env: {missing}",
                            "meta": {"code": "MISSING_ENV", "tool": tool_name, "missing": missing}}
                ctx.setdefault("secrets", {}).setdefault(tool_name, {}).update(secrets)
                try:
                    res = base(args, ctx)
                    if isinstance(res, dict) and "status" in res: return res
                    return {"status":"ok","content": res}
                except Exception as e:
                    return {"status":"error","error": str(e), "meta":{"code":"EXCEPTION","tool": tool_name}}
            return wrapped
        registry[spec.name] = _wrap()
    return registry

# ---- built-in tools ----
def _safe_num(n):
    if isinstance(n, (int, float)): return n
    raise ValueError("bad number")
def _eval_ast(node):
    ops = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
           ast.Pow: op.pow, ast.Mod: op.mod, ast.UAdd: lambda x:x, ast.USub: op.neg}
    if isinstance(node, ast.Num): return _safe_num(node.n)
    if isinstance(node, ast.UnaryOp) and type(node.op) in ops: return ops[type(node.op)](_eval_ast(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in ops: return ops[type(node.op)](_eval_ast(node.left), _eval_ast(node.right))
    if isinstance(node, ast.Expression): return _eval_ast(node.body)
    raise ValueError("unsupported expression")

def tool_calculator(args, ctx) -> ToolResult:
    expr = str(args.get("expression",""))
    try:
        val = _eval_ast(ast.parse(expr, mode="eval"))
        return {"status":"ok","content": str(val)}
    except Exception as e:
        return {"status":"error","error": str(e), "meta":{"code":"BAD_EXPRESSION"}}

def tool_read_file(args, ctx) -> ToolResult:
    import os
    path = args.get("path")
    if not path or not os.path.exists(path):
        return {"status":"error","error":"file not found","meta":{"code":"DATA_MISSING","path":path}}
    with open(path,"r",encoding="utf-8") as f:
        return {"status":"ok","content": f.read()[:20000]}

def tool_write_file(args, ctx) -> ToolResult:
    import os
    path, content = args.get("path"), args.get("content","")
    if not path:
        return {"status":"error","error":"missing path","meta":{"code":"BAD_ARGS"}}
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path,"w",encoding="utf-8") as f: f.write(content)
    return {"status":"ok","content": f"wrote {len(content)} bytes to {path}"}

def tool_openai_chat(args, ctx) -> ToolResult:
    # Template. Requires OPENAI_API_KEY.
    key = (ctx.get("secrets",{}).get("openai_chat",{}) or {}).get("OPENAI_API_KEY","")
    if not key:
        return {"status":"error","error":"missing key","meta":{"code":"MISSING_ENV"}}
    return {"status":"error","error":"not wired","meta":{"code":"NOT_WIRED"}}

BUILTIN_SPECS: Dict[str, ToolSpec] = {
    "calculator": ToolSpec(name="calculator", fn=tool_calculator),
    "read_file": ToolSpec(name="read_file", fn=tool_read_file),
    "write_file": ToolSpec(name="write_file", fn=tool_write_file),
    "openai_chat": ToolSpec(name="openai_chat", fn=tool_openai_chat, requires_env=["OPENAI_API_KEY"]),
}

def build_registry_by_names(names: List[str]) -> Dict[str, ToolFn]:
    specs = [BUILTIN_SPECS[n] for n in names if n in BUILTIN_SPECS]
    return make_tool_registry(specs)
