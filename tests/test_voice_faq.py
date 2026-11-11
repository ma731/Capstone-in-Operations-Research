"""Gridshift voice: offline answers to project questions.

Paraphrases must land on the right topic, plans and live checks must keep their routes,
and every number an answer quotes must match the archived snapshot it came from.
No network, no audio.
"""
import csv
import json
import re
from pathlib import Path

import pytest

pytest.importorskip("rdflib")
pytest.importorskip("owlrl")

from agentic import console, faq  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "docs" / "results_snapshots"

# worded differently from the examples inside faq.py on purpose
PARAPHRASES = {
    "overview": ["In a nutshell, what is this thesis?", "Can you sum up the capstone for me?"],
    "research_questions": ["Which questions does the thesis answer?", "Remind me of RQ1, RQ2 and RQ3"],
    "who": ["Who was the supervisor?", "Who made this?"],
    "contribution": ["What's the novelty compared with the literature?", "What does this add beyond Hall et al?"],
    "method": ["How does the optimisation model actually work?", "Explain the methodology"],
    "ambiguity_set": ["Explain the Wasserstein ambiguity set", "What does the ambiguity ball look like?"],
    "epsilon": ["How was the Wasserstein radius tuned?", "How do you pick epsilon?"],
    "feasible_set": ["Which constraints are in the model?", "Tell me about the ramp and capacity constraints"],
    "feasible_revision": ["Why did you remove the aggregate power cap?",
                          "Is the null result just an artefact of the constraints?"],
    "why_dro": ["Why DRO instead of stochastic programming?",
                "Why not just use classical robust optimisation?", "Why did you choose DRO?"],
    "why_cvar": ["Why use CVaR rather than average emissions?", "Why focus on the worst days?"],
    "falsification": ["What is the shuffled-marginals experiment?", "Was the experiment pre-registered?"],
    "solver": ["Which solver did you use and how fast is it?", "Do I need Gurobi for this?"],
    "data": ["Where did the carbon data come from?", "What's the training and test split?"],
    "grids": ["Which grids are in the study?", "What are the three portfolios?"],
    "europe": ["Did this work in Spain and France too?", "Does it generalise to Europe?"],
    "baselines": ["What did you benchmark against?", "How does it compare with a greedy heuristic?"],
    "carbon_accounting": ["How are the emissions calculated?", "Do you use marginal or average carbon intensity?"],
    "rq1": ["How much does migration save?", "Is moving jobs between regions worth it?"],
    "transfer_budget": ["How big does the transfer budget need to be?", "Where does the saving plateau?"],
    "rq2": ["Does the spatial correlation matter?", "Does modelling covariance improve anything?"],
    "mean_dominance": ["Why doesn't the correlation help?", "Explain mean dominance"],
    "copulas": ["Did copulas help?", "What about a Clayton copula?"],
    "rq3": ["Does robust optimisation pay?", "When does robustness pay off?", "Is DRO worth it?"],
    "severity": ["How severe do real grid emergencies get?", "What does the severity M mean?"],
    "online": ["How does it behave in a rolling horizon?", "What happens when the day-ahead forecast is wrong?"],
    "null_result": ["Isn't a null result just a failure?", "Why is the null result still substantive?",
                    "So you basically found nothing?"],
    "robustness_checks": ["How robust is the finding?", "What sensitivity checks did you run?"],
    "significance": ["Is the result statistically significant?", "Explain the TOST equivalence test"],
    "one_day_vs_thesis": ["Why does the console say 14% when the thesis says 4%?",
                          "Why is the one-day saving so much bigger?"],
    "recommendation": ["What's the business takeaway?", "What would you recommend to a company?"],
    "limitations": ["What are the main limitations?", "What are the weaknesses of your work?"],
    "migration_cost": ["Isn't migrating work expensive?", "What about latency and bandwidth?"],
    "future": ["What are the next steps?", "What would you improve with more time?"],
    "reproducibility": ["Can someone reproduce the results?", "Why should I trust these numbers?"],
    "agentic": ["Why is it a workflow and not an autonomous agent?", "Explain the agent layer"],
    "ontology": ["What does the ontology do?", "How many triples does the reasoner infer?"],
    "monitoring": ["How does the drift monitoring work?", "What is the MLOps side?"],
    "tools": ["What MCP tools are there?", "How can other agents use it over A2A?"],
    "evals": ["How do you evaluate the agent?", "How accurate is the routing?"],
    "human_loop": ["Is there a human in the loop?", "Can it move work by itself?"],
    "voice_tech": ["Are you an LLM?", "How does your voice work?"],
    "forecast": ["Which forecasting model is behind it?", "Why not use machine learning to predict carbon?"],
    "production": ["How would this be deployed for real?", "What would a production rollout look like?"],
    "run_demo": ["How do I run the demo?", "How do I start the console on my laptop?"],
}


def test_at_least_thirty_topics_and_each_is_covered():
    assert len(faq.TOPICS) >= 30
    assert set(PARAPHRASES) == set(faq.BY_KEY)


@pytest.mark.parametrize("key,text", [(k, t) for k, ts in PARAPHRASES.items() for t in ts])
def test_paraphrases_reach_their_topic(key, text):
    intent, args = console.classify(text)
    assert (intent, args.get("topic")) == ("faq", key), faq.scores(text)[:3]


@pytest.mark.parametrize("text,intent", [
    ("Plan the model training for June 15th", "propose_migration"),
    ("Where can the nightly ETL move?", "migration_options"),
    ("Can the checkout API move?", "migration_options"),
    ("Is the forecast drifting?", "drift"),
    ("Any drift alerts this year?", "drift"),
    ("List the jobs", "list_jobs"),
    ("What does CVaR mean here?", "metrics"),
    ("What did the thesis find?", "findings"),
    ("Tell me the results", "findings"),
    ("Who are you?", "about"),
    ("What can I ask?", "help"),
    ("help", "help"),
    ("Help me with the thing", "help"),
    ("Does it help?", "clarify"),
    ("purple elephant sandwich", "clarify"),
])
def test_existing_routes_still_win(text, intent):
    assert console.classify(text)[0] == intent


def test_router_eval_is_untouched():
    from agentic import evals, router

    rows = [router.route(c["q"]) for c in evals.CASES]
    assert all(r["intent"] == c["intent"] for r, c in zip(rows, evals.CASES))


def _sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text.strip()) if s]


@pytest.mark.parametrize("key", list(faq.BY_KEY))
def test_answers_are_short_plain_and_speakable(key):
    a = console.faq_answer(key)
    cap, tts = a["speech"]["caption"], a["speech"]["tts"]
    assert 2 <= len(_sentences(cap)) <= 4, cap
    assert "{" not in cap and "Source:" in a["answer"]
    assert "%" not in tts and not re.search(r"\bDRO\b|\bCVaR\b|\bMCP\b", tts)
    assert "—" not in a["answer"] and "–" not in a["answer"]


def test_help_lists_the_topics():
    a = console.ask("what can I ask?")
    assert a["intent"] == "help" and len(a["data"]["topics"]) == len(faq.TOPICS)
    cap = a["speech"]["caption"]
    for word in ("method", "data", "null", "limitations", "DRO", "carbon", "agent", "demo"):
        assert word in cap


def test_ask_returns_faq_answer_with_view_and_context():
    a = console.ask("Why DRO and not stochastic programming?", {"job": "llm_training"})
    assert a["intent"] == "faq" and a["args"] == {"topic": "why_dro"} and a["context"] == {"job": "llm_training"}
    assert a["data"]["title"] and a["answer"].startswith(a["speech"]["caption"])
    assert console.ask("Does modelling correlation help?")["view"] == "evidence"
    assert console.ask("What does the ontology do?")["view"] == "knowledge"


def test_live_counts_are_filled_in():
    from agentic import a2a, evals, knowledge

    ont = console.faq_answer("ontology")["speech"]["caption"]
    assert str(len(knowledge.graph(False))) in ont and str(len(knowledge.graph(True))) in ont
    assert f"{len(evals.CASES)} plain-language" in console.faq_answer("evals")["speech"]["caption"]
    assert f"{len(a2a.SKILLS)} skills" in console.faq_answer("tools")["speech"]["caption"]
    assert "1.5 times" in console.faq_answer("monitoring")["speech"]["caption"]


def test_small_numbers_keep_two_figures_when_spoken():
    assert "0.36 percent" in console.to_tts("the largest was 0.36% of CVaR")
    assert "0.06 percent" in console.to_tts("under 0.06%")
    assert "14.4 percent" in console.to_tts("14.4%")


# ------------------------------------------------------------------ numbers vs snapshots

def _rows(name):
    with open(SNAP / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _say(key):
    return faq.BY_KEY[key]["say"]


def test_rq1_and_budget_numbers_match_snapshots():
    tv = {r["grid"]: float(r["reduction_pct"]) for r in _rows("part3_transfer_value_2026-06-15.csv")}
    s = _say("rq1")
    for g in ("us_west", "taskc", "us_hetero"):
        assert f"{tv[g]:.1f}%" in s
    curve = {(r["grid"], r["budget_frac"]): float(r["cvar_reduction_pct"])
             for r in _rows("transfer_value_curve_2026-06-24.csv")}
    s = _say("transfer_budget")
    assert f"{curve[('taskc', '0.1')]:.1f}%" in s and f"{curve[('us_hetero', '0.1')]:.1f}%" in s
    assert curve[("us_west", "0.1")] >= curve[("us_west", "0.2")]   # "already at its plateau"


def test_rq2_numbers_match_snapshots():
    rows = [r for r in _rows("bh_correction.csv") if not r.get("variant", "").startswith("ablate")]
    gaps = [abs(float(r["gap_pct"])) for r in rows]
    assert len(gaps) == 144 and "144" in _say("rq2")
    assert "0.35%" in _say("rq2") and round(max(gaps), 2) == 0.35 and max(gaps) < 0.4
    ta = [abs(float(r["gap_pct"])) for r in _rows("taskA_regimes_2026-06-02.csv")]
    assert len(ta) == 9 and max(ta) < 0.06 and "under 0.06%" in _say("feasible_revision")


def test_rq3_numbers_match_snapshots():
    sev = {(r["kind"], r["key"]): float(r["severity"]) for r in _rows("carbon_ceiling_2026-06-24.csv")}
    joint = [v for (k, _), v in sev.items() if k == "joint"]
    s = _say("rq3")
    assert f"{min(joint):.2f} to {max(joint):.2f}" in s
    regions = sorted(v for (k, _), v in sev.items() if k == "region")
    assert len(regions) == 17 and f"{regions[8]:.2f}" in _say("severity")
    em = [r for r in _rows("part3_emergency_2026-06-15.csv") if r["grid"] == "us_west"]
    first = min(float(r["M"]) for r in em if r["significant"] == "True")
    assert first == 3.0 and "about 3 times" in s


def test_online_and_baseline_numbers_match_snapshots():
    on = {r["grid"]: float(r["cvar_gap_pct"]) for r in _rows("part4_online_2026-06-15.csv")}
    s = _say("online")
    assert f"+{on['us_west']:.2f}%" in s and f"+{on['taskc']:.2f}%" in s and f"{-on['us_hetero']:.1f}% worse" in s
    eb = {(r["grid"], r["policy"]): float(r["cvar_reduction_vs_agnostic_pct"])
          for r in _rows("external_baselines_2026-07-12.csv")}
    s = _say("baselines")
    for g in ("us_west", "taskc", "us_hetero"):
        assert f"{eb[(g, 'LP_transfer')]:.1f}%" in s and f"{eb[(g, 'B1_greedy_time_shift')]:.1f}%" in s


def test_findings_figures_still_match_snapshots():
    # the older hard-coded figures in console.FIGURES, checked against the CSVs
    tv = [float(r["reduction_pct"]) for r in _rows("part3_transfer_value_2026-06-15.csv")]
    f = console.FIGURES
    assert round(min(tv), 1) == f["RQ1"]["low_pct"] and round(max(tv), 1) == f["RQ1"]["high_pct"]
    joint = [float(r["severity"]) for r in _rows("carbon_ceiling_2026-06-24.csv") if r["kind"] == "joint"]
    assert [round(min(joint), 2), round(max(joint), 2)] == f["RQ3"]["observed_severity_x"]


def test_no_long_dashes_in_faq_module():
    text = (ROOT / "agentic" / "faq.py").read_text(encoding="utf-8")
    assert "—" not in text and "–" not in text
    json.dumps(console.help_answer())   # serialisable
