"""Gridshift console: router dates, speech, graph export, voice fallback, HTTP smoke, plan detail.

Skipped without the agentic extras, like test_agentic.py. Tests that need the licensed
Electricity Maps data skip when it is not installed. No network.
"""
import json
import threading
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("rdflib")
pytest.importorskip("owlrl")

from agentic import console, knowledge, router, voice  # noqa: E402
from agentic.findings import FINDINGS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
needs_data = pytest.mark.skipif(not console.data_available(), reason="licensed Electricity Maps data not installed")


# ------------------------------------------------------------------ router dates

@pytest.mark.parametrize("text,expected", [
    ("Plan the model training for June 15th", date(2025, 6, 15)),
    ("plan it for Jun. 3rd, 2023", date(2023, 6, 3)),
    ("june 15 2024", date(2024, 6, 15)),
    ("on 15 June", date(2025, 6, 15)),
    ("the 15th of June 2024", date(2024, 6, 15)),
    ("June fifteenth", date(2025, 6, 15)),
    ("july twenty-first", date(2025, 7, 21)),
    ("today", date(2025, 6, 15)),
    ("yesterday", date(2025, 6, 14)),
    ("tomorrow", date(2025, 6, 16)),
    ("Sept 9", date(2025, 9, 9)),
    ("2024-01-02, not June 3rd", date(2024, 1, 2)),     # ISO wins
    ("Feb 30", router.DEFAULT_DAY),                     # invalid falls back
    ("no date here", router.DEFAULT_DAY),
    ("the 5 regions may move", router.DEFAULT_DAY),     # "may" the verb is not a month
])
def test_router_parses_spoken_dates(text, expected):
    assert router._day(text) == expected


def test_has_explicit_day():
    assert router.has_explicit_day("What about July 4th?")
    assert router.has_explicit_day("2025-01-01")
    assert not router.has_explicit_day("Where can it move?")


def test_new_aliases_route_to_the_right_job():
    assert router._job("plan the training run") == "llm_training"
    assert router._job("the data pipeline") == "nightly_etl"
    assert router._job("can the check out move") == "checkout_api"


def test_labelled_eval_still_perfect():
    from agentic import evals

    res = evals.run() if console.data_available() else None
    if res is None:
        rows = [router.route(c["q"]) for c in evals.CASES]
        assert all(r["intent"] == c["intent"] for r, c in zip(rows, evals.CASES))
    else:
        assert res["routing_accuracy"] == 1.0 and res["end_to_end_accuracy"] == 1.0


# ------------------------------------------------------------------ speech

def test_to_tts_normalises_units_numbers_acronyms_and_dates():
    t = console.to_tts("Moving 36.0 MWh at 14.4% on 2025-06-15 cuts 1.48x; A2A and MCP and the ETL, "
                       "250 gCO2eq/kWh in US-NY-NYIS, 2025-08.")
    assert "36 megawatt hours" in t and "14.4 percent" in t and "June 15th, 2025" in t
    assert "1.48 times" in t and "A to A" in t and "M C P" in t and "E T L" in t
    assert "grams of carbon per kilowatt hour" in t and "New York" in t and "August 2025" in t
    assert console.to_tts("22.48 t") == "22.5 tonnes"


def test_no_long_dashes_in_any_speech():
    s = console.speech("one \u2014 two \u2013 three")
    assert "\u2014" not in json.dumps(s, ensure_ascii=False) and "\u2013" not in json.dumps(s, ensure_ascii=False)
    blob = json.dumps(console.lines(), ensure_ascii=False) + json.dumps(console.findings(), ensure_ascii=False)
    assert "\u2014" not in blob and "\u2013" not in blob


def test_figures_match_the_findings_text():
    f = console.FIGURES
    assert f"{f['RQ1']['low_pct']:.1f}" in FINDINGS["RQ1"] and f"{f['RQ1']['high_pct']:.1f}" in FINDINGS["RQ1"]
    assert f"{f['RQ2']['max_gain_pct']:g}%" in FINDINGS["RQ2"]
    assert f"{f['RQ3']['breakeven_severity_x']:g}x" in FINDINGS["RQ3"]
    lo, hi = f["RQ3"]["observed_severity_x"]
    assert f"{lo}-{hi}x" in FINDINGS["RQ3"]


# ------------------------------------------------------------------ graph

def test_graph_export_counts_and_rules():
    g = knowledge.graph_export()
    assert g["counts"]["asserted_triples"] == len(knowledge.graph(False))
    assert g["counts"]["reasoned_triples"] == len(knowledge.graph(True))
    edges = g["edges"]
    assert all(e["source"] != e["target"] for e in edges)
    ids = {n["id"] for n in g["nodes"]}
    assert all(e["source"] in ids and e["target"] in ids for e in edges)
    assert any(e["source"] == "llm_training" and e["target"] == "FlexibleJob" and e["inferred"] for e in edges)
    reach = [e for e in edges if e["predicate"] == "reachableRegion"]
    assert reach and all(e["rule"] == "property chain" and e["inferred"] for e in reach)
    assert all(e["rule"] == "owl:inverseOf" for e in edges if e["predicate"] == "hasRegion")
    dc = [e for e in edges if e["source"] == "dc_sacramento" and e["target"] == "DataCenter"]
    assert dc and dc[0]["rule"] == "rdfs:domain"
    assert {n["zone"] for n in g["nodes"] if n["kind"] == "region"} >= {"US-CAL-CISO", "CA-ON"}


# ------------------------------------------------------------------ voice

def test_voice_off_raises_and_cache_path_is_stable(monkeypatch):
    monkeypatch.setenv("GRIDSHIFT_TTS", "off")
    assert voice.engine() is None and voice.engine_name() == "none"
    with pytest.raises(voice.TTSUnavailable):
        voice.synthesize("a line nobody has ever cached 7f3a9c")
    assert voice.cache_path("x") == voice.cache_path("x") and voice.cache_path("x").suffix == ".mp3"


# ------------------------------------------------------------------ HTTP smoke

@pytest.fixture(scope="module")
def server():
    from agentic import serve

    srv = serve.make_server("127.0.0.1", 0, quiet=True)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def _get(url, data=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


@pytest.mark.parametrize("path", ["/api/health", "/api/meta", "/api/graph", "/api/findings",
                                  "/.well-known/agent-card.json", "/api/interfaces"])
def test_http_json_endpoints(server, path):
    status, headers, body = _get(server + path)
    assert status == 200
    assert headers["Content-Type"].startswith("application/json") and headers["Cache-Control"] == "no-store"
    json.loads(body)


def test_http_health_and_meta_shape(server):
    h = json.loads(_get(server + "/api/health")[2])
    assert h["ok"] and h["ontology"] == {"asserted_triples": 169, "reasoned_triples": 577}
    m = json.loads(_get(server + "/api/meta")[2])
    assert len(m["zones"]) == 11 and len(m["lens"]) == 6 and len(m["jobs"]) == 4
    assert {"greeting", "mic_unavailable", "data_offline", "ui"} <= set(m["lines"])


def test_http_a2a_static_and_traversal(server):
    status, _, body = _get(server + "/a2a", {"jsonrpc": "2.0", "id": 1, "method": "message/send",
                                             "params": {"message": {"parts": [{"kind": "text",
                                                                               "text": "List the jobs"}]}}})
    assert status == 200 and json.loads(body)["result"]["status"]["state"] == "completed"
    req = urllib.request.Request(server + "/a2a", data=b"{bad", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        assert json.loads(r.read())["error"]["code"] == -32700
    index = (ROOT / "agentic" / "web" / "index.html").is_file()
    assert _get(server + "/")[0] == (200 if index else 404)

    import http.client
    host, port = server.rsplit("/", 1)[1].split(":")
    c = http.client.HTTPConnection(host, int(port), timeout=10)
    c.request("GET", "/../pyproject.toml")
    assert c.getresponse().status == 404
    c.close()


def test_http_tts_off_gives_503(server, monkeypatch):
    monkeypatch.setenv("GRIDSHIFT_TTS", "off")
    status, _, body = _get(server + "/api/tts?text=" + urllib.request.quote("never cached 91b2e"))
    assert status == 503 and json.loads(body)["error"]["code"] == "tts_unavailable"
    assert _get(server + "/api/tts?text=")[0] == 400


def test_http_errors_have_the_contract_shape(server):
    status, _, body = _get(server + "/api/plan?share=2")
    err = json.loads(body)["error"]
    assert status == 422 and err["code"] == "out_of_range" and set(err["speech"]) == {"caption", "tts"}
    assert _get(server + "/api/nope")[0] == 404


def test_decision_is_logged_and_never_executed():
    r = console.decide({"job": "llm_training", "day": "2025-06-15", "share": 0.3, "decision": "approve", "by": "t"})
    assert r["status"] == "APPROVED_NOT_EXECUTED" and r["executed"] is False and r["audit"][0]["id"] == r["id"]
    assert console.decide({"decision": "reject"})["status"] == "REJECTED"
    with pytest.raises(console.BadRequestError):
        console.decide({"decision": "maybe"})


def test_no_data_mode_hides_one_day_numbers(monkeypatch):
    monkeypatch.setenv("GRIDSHIFT_NO_DATA", "1")
    assert not console.data_available()
    with pytest.raises(console.DataUnavailableError):
        console.plan("llm_training", "2025-06-15", 0.3)
    a = console.ask("Plan the model training for June 15th")
    assert a["intent"] == "propose_migration" and a["data"] is None
    s08 = next(s for s in console.present()["steps"] if s["id"] == "s08")
    assert not any(ch.isdigit() for ch in s08["speech"]["caption"])
    assert console.plan("checkout_api", "2025-06-15")["status"] == "NOT_MOVABLE"   # needs no data


# ------------------------------------------------------------------ data

PLAN_KEYS = {"day", "zones", "work_mwh", "transfer_budget_mwh", "moved_mwh", "net_shift_mwh_by_zone",
             "tonnes_time_shift_only", "tonnes_with_migration", "saving_pct", "note"}


@needs_data
def test_plan_day_without_detail_is_unchanged():
    from agentic import scheduler

    zones = knowledge.migration_options("llm_training")["allowed_zones"]
    plain = scheduler.plan_day(zones, date(2025, 6, 15))
    rich = scheduler.plan_day(zones, date(2025, 6, 15), detail=True)
    assert set(plain) == PLAN_KEYS
    assert {k: rich[k] for k in PLAN_KEYS} == plain


@needs_data
def test_plan_detail_shapes_and_flow_invariants():
    p = console.plan("llm_training", "2025-06-15", 0.3)
    assert p["plan"]["saving_pct"] == 14.4
    pl, h = p["plan"], p["plan"]["hourly"]
    for key in ("forecast_g_per_kwh", "actual_g_per_kwh", "load_flat_mwh", "load_time_shift_mwh",
                "load_with_migration_mwh"):
        assert set(h[key]) == set(pl["zones"]) and all(len(v) == 24 for v in h[key].values())
    assert all(len(v) == 24 for v in h["tonnes_by_hour"].values())
    for f in pl["flows"]:
        assert sum(f["by_hour_mwh"]) == pytest.approx(f["mwh"], abs=1e-6)
    gained = sum(v for v in pl["net_shift_mwh_by_zone"].values() if v > 0)
    assert sum(f["mwh"] for f in pl["flows"]) == pytest.approx(gained, abs=1e-2)
    load = np.array([h["load_with_migration_mwh"][z] for z in pl["zones"]])
    act = np.array([h["actual_g_per_kwh"][z] for z in pl["zones"]])
    assert (load * act).sum() / 1000 == pytest.approx(pl["tonnes_with_migration"], abs=1e-3)
    assert p["illustration"] is True and p["approval"]["executed"] is False
    assert [s["n"] for s in p["steps"]] == [1, 2, 3, 4, 5]


@needs_data
def test_plan_steps_have_plain_headlines_and_backtest_speech():
    p = console.plan("llm_training", "2025-06-15", 0.3)
    heads = [s["headline"] for s in p["steps"]]
    assert heads[0] == "Checked the rules: this job is allowed to move between these 5 regions"
    assert all(h and "Ontology" not in h for h in heads) and "would have" in heads[3]
    assert any("reachableRegion" in line for line in p["steps"][0]["lines"])   # detail kept
    assert "would have" in p["speech"]["caption"] and "one-day illustration" in p["speech"]["caption"]
    s08 = next(s for s in console.present()["steps"] if s["id"] == "s08")["speech"]["caption"]
    assert "would have cut" in s08 and "one-day illustration" in s08


def test_fixed_job_step_headline():
    p = console.plan("checkout_api", "2025-06-15")
    assert [s["n"] for s in p["steps"]] == [1] and "stays where it is" in p["steps"][0]["headline"]


@needs_data
def test_nightly_etl_and_sweep():
    assert console.plan("nightly_etl", "2025-06-15", 0.3)["plan"]["saving_pct"] == 36.99
    sw = console.sweep("llm_training", "2025-06-15", "0,0.1,0.2,0.3,0.4,0.5")
    savings = [p["saving_pct"] for p in sw["points"]]
    assert savings[0] == 0 and savings == sorted(savings)


@needs_data
def test_ask_plans_spoken_dates_and_follows_up():
    a = console.ask("Plan the model training for June 15th")
    assert a["intent"] == "propose_migration" and a["args"] == {"job": "llm_training", "day": "2025-06-15"}
    assert a["view"] == "command" and a["data"]["plan"]["saving_pct"] == 14.4
    b = console.ask("What about July 4th?", a["context"])
    assert b["intent"] == "propose_migration" and b["args"] == {"job": "llm_training", "day": "2025-07-04"}
    assert console.ask("Is the forecast drifting?")["view"] == "monitor"


@needs_data
def test_present_script_has_sixteen_steps_with_live_numbers():
    pr = console.present()
    assert [s["id"] for s in pr["steps"]] == [f"s{i:02d}" for i in range(1, 17)]
    s08 = next(s for s in pr["steps"] if s["id"] == "s08")["speech"]["caption"]
    assert "14.4 percent" in s08


# ------------------------------------------------------------------ copy rule

def test_no_em_or_en_dashes_in_new_files():
    files = [ROOT / "agentic" / f for f in ("serve.py", "console.py", "voice.py", "faq.py", "warm_cache.py", "scheduler.py",
                                             "workflow.py", "router.py", "knowledge.py")]
    files.append(Path(__file__))
    web = ROOT / "agentic" / "web"
    if web.is_dir():
        files += [p for p in web.rglob("*") if p.is_file() and p.suffix in {".html", ".js", ".css", ".svg", ".json"}]
    bad = [str(p) for p in files if any(ch in p.read_text(encoding="utf-8") for ch in ("\u2014", "\u2013"))]
    assert not bad, bad
