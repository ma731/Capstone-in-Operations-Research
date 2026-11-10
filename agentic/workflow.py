"""A linear workflow, not an agent: ontology check → forecast → plan → explain → approval.

Why a workflow. The decision here is an optimisation with guarantees (budgets,
capacities, a solver that proves optimality). Letting a language model choose the
steps would add cost and risk and buy nothing. So the steps are fixed, each one is
code, and the only judgement call, whether to actually move the work, stays with a
person. An agent (Claude, a Copilot) can still use this through the MCP server: it
asks; the workflow answers with a draft; a person approves.

Nothing here moves any work. The output is always a proposal pending approval.
"""
from __future__ import annotations

from datetime import date

from . import knowledge, scheduler

APPROVER = "operations lead"
APPROVAL_REASON = ("Moving work between regions changes where data is processed (data residency, "
                   "contracts and capacity commitments), so a person signs it off.")


def propose(job: str, day: date, transfer_share: float = 0.3) -> dict:
    steps = []
    options = knowledge.migration_options(job)
    steps.append({"step": "1. ontology check", "result": options["why"]})
    if not options.get("known"):
        return {"job": job, "status": "UNKNOWN_JOB", "steps": steps}
    if not options["flexible"]:
        return {"job": job, "status": "NOT_MOVABLE", "home_zone": options.get("home_zone"), "steps": steps}

    zones = options["allowed_zones"]
    plan = scheduler.plan_day(zones, day, transfer_share=transfer_share)
    steps.append({"step": "2. forecast", "result": f"14-day seasonal forecast for {len(zones)} regions on {day}."})
    steps.append({"step": "3. plan", "result": f"Time shifting only vs moving up to {transfer_share:.0%} of the work "
                                               f"between {', '.join(zones)}."})
    gainers = [z for z, v in plan["net_shift_mwh_by_zone"].items() if v > 0]
    losers = [z for z, v in plan["net_shift_mwh_by_zone"].items() if v < 0]
    summary = (f"On {day}, moving {plan['moved_mwh']} MWh of {plan['work_mwh']:.0f} MWh "
               f"from {', '.join(losers) or 'nowhere'} to {', '.join(gainers) or 'nowhere'} would have cut that day's "
               f"emissions from {plan['tonnes_time_shift_only']} t to {plan['tonnes_with_migration']} t "
               f"({plan['saving_pct']}% less), scored on the carbon that actually happened.")
    steps.append({"step": "4. explain", "result": summary})
    steps.append({"step": "5. approval", "result": f"Pending: {APPROVER}. {APPROVAL_REASON}"})
    defs = knowledge.metrics()
    return {"job": job, "status": "PENDING_APPROVAL", "approval_required_from": APPROVER,
            "approval_reason": APPROVAL_REASON, "executed": False, "summary": summary,
            "plan": plan, "steps": steps, "pattern": "linear workflow (fixed steps, code only, human approval)",
            "metric_definitions": {k: defs[k] for k in ("emissions_tonnes", "saving_pct", "moved_mwh")}}
