from ai_agent.core import run_cycle
from ai_agent.hooks import draft_rule_based, decide_simple, finalize_min
from ai_agent.tools import build_registry_by_names

def test_percent_math():
    hooks = {"draft": draft_rule_based, "decide": decide_simple, "finalize": finalize_min}
    tools = build_registry_by_names(["calculator"])
    result = run_cycle("calc 19.5% of 349", hooks=hooks, tools=tools, max_actions=1)
    assert abs(float(result["final_text"]) - 68.055) < 1e-9
    # or format expected: f"{0.195*349:.3f}"

