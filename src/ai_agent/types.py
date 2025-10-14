from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TypedDict, Literal

Status = Literal["ok", "error", "skipped"]

class ToolResult(TypedDict, total=False):
    status: Status
    content: Any
    error: str
    meta: Dict[str, Any]

ToolFn = Callable[[Dict[str, Any], Dict[str, Any]], ToolResult]

class Draft(TypedDict, total=False):
    intent: str
    expression: str
    message: str

class Decision(TypedDict, total=False):
    kind: str           # "answer" | "use_tool"
    tool: str
    args: Dict[str, Any]
    text: str

class Gate(TypedDict, total=False):
    issues: List[Dict[str, Any]]
    severity: float
    intervene: bool
    reason: str
    user_plan: Optional[Dict[str, Any]]

Hooks = Dict[str, Callable[..., Any]]

@dataclass
class ToolSpec:
    name: str
    fn: ToolFn
    description: str = ""
    requires_env: List[str] = field(default_factory=list)
