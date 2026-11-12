"""A small labelled eval: plain-language requests with the answer we expect.

    python -m agentic.evals

Two scores: did the router pick the right tool (and job), and did the end-to-end
answer land in the expected state (a fixed job is never proposed for migration, an
unclear request asks back). Every change to the router, the ontology or the workflow
is checked against the same cases, the way the thesis checks every number.
"""
from __future__ import annotations

from . import a2a, router

CASES = [
    {"q": "Where can the nightly ETL pipeline move?", "intent": "migration_options", "job": "nightly_etl", "state": "completed"},
    {"q": "Can the checkout API move to Nevada?", "intent": "migration_options", "job": "checkout_api", "state": "completed",
     "flexible": False},
    {"q": "Plan the model training for 2025-06-15", "intent": "propose_migration", "job": "llm_training", "state": "completed",
     "status": "PENDING_APPROVAL"},
    {"q": "Propose a schedule for the risk simulation", "intent": "propose_migration", "job": "risk_batch", "state": "completed",
     "status": "PENDING_APPROVAL"},
    {"q": "Schedule the checkout API somewhere cleaner", "intent": "propose_migration", "job": "checkout_api", "state": "completed",
     "status": "NOT_MOVABLE"},
    {"q": "Does robust optimisation pay?", "intent": "findings", "state": "completed"},
    {"q": "What does CVaR mean here?", "intent": "metrics", "state": "completed"},
    {"q": "List the jobs", "intent": "list_jobs", "state": "completed"},
    {"q": "Help me with the thing", "intent": "clarify", "state": "input-required"},
]


def run() -> dict:
    rows, route_ok, end_ok = [], 0, 0
    for c in CASES:
        r = router.route(c["q"])
        routed = r["intent"] == c["intent"] and r["args"].get("job") == c.get("job")
        state, _, data = a2a.answer(c["q"])
        ok = state == c["state"]
        if "status" in c:
            ok = ok and data.get("status") == c["status"]
        if "flexible" in c:
            ok = ok and data.get("flexible") == c["flexible"]
        route_ok += routed
        end_ok += ok
        rows.append({"q": c["q"], "routed": routed, "end_to_end": ok})
    n = len(CASES)
    return {"cases": n, "routing_accuracy": route_ok / n, "end_to_end_accuracy": end_ok / n, "rows": rows}


if __name__ == "__main__":
    res = run()
    print(f"{res['cases']} cases | routing {res['routing_accuracy']:.0%} | end to end {res['end_to_end_accuracy']:.0%}")
    for row in res["rows"]:
        print(f"  {'ok ' if row['routed'] and row['end_to_end'] else 'MISS'}  {row['q']}")
