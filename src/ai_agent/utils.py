from __future__ import annotations
import json, os, time
from typing import Any, Dict, List

def mem_path() -> str:
    p = ".agents/memory.jsonl"
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p

def mem_write(event: Dict[str, Any]) -> None:
    event = dict(event); event["ts"] = time.time()
    with open(mem_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

def mem_tail(n: int = 20) -> List[Dict[str, Any]]:
    p = mem_path()
    if not os.path.exists(p): return []
    out: List[Dict[str, Any]] = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            try: out.append(json.loads(line))
            except json.JSONDecodeError: pass
    return out[-n:]
