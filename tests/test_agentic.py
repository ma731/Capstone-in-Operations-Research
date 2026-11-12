"""The post-capstone extension: ontology inference, the approval workflow, the MCP server.

Skipped when the optional extras are not installed (pip install -e .[agentic]), so the
thesis test suite is unaffected.
"""
import asyncio
from datetime import date, timedelta

import pytest

pytest.importorskip("rdflib")
pytest.importorskip("owlrl")

from agentic import knowledge, workflow  # noqa: E402

WEST = ["US-CAL-BANC", "US-CAL-CISO", "US-CAL-LDWP", "US-NW-NEVP", "US-SW-AZPS"]


def test_subclass_inference_types_a_training_job_as_flexible():
    assert knowledge.types_of("llm_training", reason=False) == ["TrainingJob"]
    assert {"TrainingJob", "FlexibleJob", "Job"} <= set(knowledge.types_of("llm_training"))


def test_domain_inference_types_an_untyped_data_centre():
    assert knowledge.types_of("dc_sacramento", reason=False) == []
    assert "DataCenter" in knowledge.types_of("dc_sacramento")


def test_property_chain_gives_the_portfolio_regions():
    assert knowledge.migration_options("llm_training")["allowed_zones"] == WEST


def test_portfolios_stay_separate_although_caiso_is_in_two():
    assert knowledge.migration_options("risk_batch")["allowed_zones"] == ["US-CAL-CISO", "US-NW-BPAT", "US-TEX-ERCO"]


def test_a_fixed_job_never_moves():
    o = knowledge.migration_options("checkout_api")
    assert not o["flexible"] and o["allowed_zones"] == ["US-CAL-CISO"]
    assert workflow.propose("checkout_api", date(2025, 6, 15))["status"] == "NOT_MOVABLE"


def test_unknown_job_is_refused():
    assert workflow.propose("nope", date(2025, 6, 15))["status"] == "UNKNOWN_JOB"


def test_proposal_is_a_draft_within_budget_and_never_worse():
    p = workflow.propose("llm_training", date(2025, 6, 15), transfer_share=0.3)
    plan = p["plan"]
    assert p["status"] == "PENDING_APPROVAL" and p["executed"] is False
    assert plan["moved_mwh"] <= plan["transfer_budget_mwh"] + 1e-6
    assert abs(sum(plan["net_shift_mwh_by_zone"].values())) < 1e-3   # work is moved, not created
    assert [s["step"][0] for s in p["steps"]] == ["1", "2", "3", "4", "5"]


def test_zero_budget_means_no_saving():
    p = workflow.propose("nightly_etl", date(2025, 6, 15), transfer_share=0.0)
    assert p["plan"]["moved_mwh"] == pytest.approx(0, abs=1e-6)
    assert p["plan"]["saving_pct"] == pytest.approx(0, abs=1e-6)


def test_mcp_server_exposes_read_only_tools_and_a_draft_tool():
    pytest.importorskip("mcp")
    from agentic import mcp_server as m

    tools = {t.name: t for t in asyncio.run(m.server.list_tools())}
    assert set(tools) == {"list_jobs", "migration_options", "propose_migration"}
    assert tools["list_jobs"].annotations.read_only_hint and tools["migration_options"].annotations.read_only_hint
    assert not tools["propose_migration"].annotations.read_only_hint
    assert not tools["propose_migration"].annotations.destructive_hint
    resources = {str(r.uri) for r in asyncio.run(m.server.list_resources())}
    assert resources == {"capstone://ontology", "capstone://metrics", "capstone://findings"}


def test_semantic_layer_defines_each_metric_once_and_infers_risk_metrics():
    m = knowledge.metrics()
    assert {"emissions_tonnes", "saving_pct", "moved_mwh", "cvar95"} <= set(m)
    assert m["cvar95"]["risk_metric"] and not m["saving_pct"]["risk_metric"]   # RiskMetric -> Metric
    p = workflow.propose("llm_training", date(2025, 6, 15))
    assert set(p["metric_definitions"]) == {"emissions_tonnes", "saving_pct", "moved_mwh"}


@pytest.mark.parametrize("text,intent,job", [
    ("Where can the nightly ETL pipeline move?", "migration_options", "nightly_etl"),
    ("Plan the model training for 2025-06-15", "propose_migration", "llm_training"),
    ("Does robust optimisation pay?", "findings", None),
    ("Help me with the thing", "clarify", None),
])
def test_router_sends_each_request_to_one_tool(text, intent, job):
    from agentic import router

    r = router.route(text)
    assert r["intent"] == intent and r["args"].get("job") == job


def test_a2a_card_and_message_send():
    from agentic import a2a

    card = a2a.agent_card("http://localhost:9000/")
    assert card["url"] == "http://localhost:9000/a2a" and len(card["skills"]) == 3
    ok = a2a.handle({"jsonrpc": "2.0", "id": 1, "method": "message/send",
                     "params": {"message": {"parts": [{"kind": "text", "text": "Where can the risk simulation move?"}]}}})
    assert ok["result"]["status"]["state"] == "completed"
    ask = a2a.handle({"jsonrpc": "2.0", "id": 2, "method": "message/send",
                      "params": {"message": {"parts": [{"kind": "text", "text": "hmm"}]}}})
    assert ask["result"]["status"]["state"] == "input-required"
    assert a2a.handle({"jsonrpc": "2.0", "id": 3, "method": "tasks/cancel"})["error"]["code"] == -32601


def test_labelled_eval_is_perfect():
    from agentic import evals

    res = evals.run()
    assert res["routing_accuracy"] == 1.0 and res["end_to_end_accuracy"] == 1.0


def _synthetic(drift_from: date | None):
    """A fake _hourly: a daily cycle plus noise that triples after drift_from."""
    import numpy as np

    def fake(zone, start, end):
        rng = np.random.default_rng(0)
        days = (end - start).days + 1
        base = 300 + 50 * np.sin(np.linspace(0, 2 * np.pi, 24))
        out = []
        for i in range(days):
            d = start + timedelta(days=i)
            sd = 30 if drift_from and d >= drift_from else 10
            out.append(base + rng.normal(0, sd, 24))
        return np.array(out)
    return fake


def test_drift_monitor_stays_quiet_on_a_stable_forecast(monkeypatch):
    from agentic import monitoring

    monkeypatch.setattr(monitoring, "_hourly", _synthetic(None))
    rep = monitoring.drift_report(["Z"], date(2025, 1, 1), date(2025, 8, 31))
    assert rep["alerts"] == [] and "stays the right choice" in rep["action"]
    assert len(rep["zones"]["Z"]["months"]) == 8


def test_drift_monitor_flags_a_worse_forecast_and_points_at_rq3(monkeypatch):
    from agentic import monitoring

    monkeypatch.setattr(monitoring, "_hourly", _synthetic(date(2025, 6, 1)))
    rep = monitoring.drift_report(["Z"], date(2025, 1, 1), date(2025, 8, 31))
    assert {a["month"] for a in rep["alerts"]} >= {"2025-07", "2025-08"}
    assert all(a["month"] >= "2025-06" for a in rep["alerts"])   # no false alarms before the shift
    assert "RQ3" in rep["action"]
    assert "DRIFT" in monitoring.to_markdown(rep, "test")
