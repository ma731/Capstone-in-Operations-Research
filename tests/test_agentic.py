"""The post-capstone extension: ontology inference, the approval workflow, the MCP server.

Skipped when the optional extras are not installed (pip install -e .[agentic]), so the
thesis test suite is unaffected.
"""
import asyncio
from datetime import date

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
    assert resources == {"capstone://ontology", "capstone://findings"}
