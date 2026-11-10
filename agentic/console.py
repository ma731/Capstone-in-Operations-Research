"""Gridshift: the data behind the local console (agentic/serve.py).

Pure functions that return the JSON the web app reads. Every number comes from the
thesis code (ontology, optimiser, drift monitor, evals); this module only shapes it,
caches it and writes the spoken lines.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
import re
import threading
import time
import uuid
from collections import deque
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from . import knowledge, router, voice
from .findings import FINDINGS

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "raw" / "electricitymaps"
API_CACHE = Path(__file__).with_name(".cache") / "api"
CACHE_VERSION = 1
VERSION = "1.0"
START = time.time()
DEFAULT = {"job": "llm_training", "day": router.DEFAULT_DAY.isoformat(), "share": 0.3}
PORTFOLIOS = ["us_west", "taskc", "us_hetero"]

# one solve at a time: cvxpy and rdflib are not built for concurrent use
SOLVER_LOCK = threading.RLock()

ZONES = [
    {"id": "US-CAL-BANC", "name": "Sacramento", "short": "BANC", "lat": 38.6, "lon": -121.5},
    {"id": "US-CAL-CISO", "name": "California ISO", "short": "CAISO", "lat": 36.2, "lon": -119.8},
    {"id": "US-CAL-LDWP", "name": "Los Angeles", "short": "LADWP", "lat": 34.1, "lon": -118.2},
    {"id": "US-NW-NEVP", "name": "Nevada", "short": "NEVP", "lat": 36.2, "lon": -115.1},
    {"id": "US-SW-AZPS", "name": "Arizona", "short": "AZPS", "lat": 33.4, "lon": -112.1},
    {"id": "US-NW-BPAT", "name": "Bonneville", "short": "BPA", "lat": 45.6, "lon": -121.0},
    {"id": "US-TEX-ERCO", "name": "Texas", "short": "ERCOT", "lat": 31.0, "lon": -97.5},
    {"id": "US-MIDW-MISO", "name": "Midwest", "short": "MISO", "lat": 42.0, "lon": -91.0},
    {"id": "US-MIDA-PJM", "name": "Mid-Atlantic", "short": "PJM", "lat": 39.9, "lon": -77.5},
    {"id": "US-NY-NYIS", "name": "New York", "short": "NYISO", "lat": 42.9, "lon": -75.5},
    {"id": "CA-ON", "name": "Ontario", "short": "IESO", "lat": 44.0, "lon": -79.4},
]
ZONE_NAMES = {z["id"]: z["name"] for z in ZONES}

LENS = [
    {"compute": "Grid region", "supply_chain": "Plant or DC", "note": "Each has its own hourly cost: carbon intensity."},
    {"compute": "Flexible job", "supply_chain": "Order with a delivery window",
     "note": "Can wait hours or ship from another site."},
    {"compute": "Fixed job", "supply_chain": "Make-to-order at a fixed site", "note": "User-facing, never moves."},
    {"compute": "Transfer budget", "supply_chain": "Logistics capacity",
     "note": "How much work may move between sites."},
    {"compute": "Day-ahead forecast", "supply_chain": "Demand plan",
     "note": "14-day seasonal mean, monitored for drift."},
    {"compute": "Approval gate", "supply_chain": "S&OP sign-off", "note": "A person approves every cross-region move."},
]

# the numbers inside findings.FINDINGS, as numbers (a test keeps them in sync)
FIGURES = {
    "RQ1": {"metric": "out-of-sample CVaR95 reduction vs no transfer", "low_pct": 4.0, "high_pct": 9.9},
    "RQ2": {"max_gain_pct": 0.4},
    "RQ3": {"breakeven_severity_x": 3.0, "observed_severity_x": [1.29, 1.89]},
}
LADDER = [
    {"layer": "Per-region scheduler + transfer channel", "verdict": "pays", "value_label": "4.0-9.9% lower CVaR95"},
    {"layer": "Co-movement models (covariance, copulas)", "verdict": "marginal", "value_label": "under 0.4%"},
    {"layer": "Distributionally robust hedging", "verdict": "conditional",
     "value_label": "pays above ~3x severity; observed 1.29-1.89x"},
]
SUGGESTIONS = ["Plan the model training for June 15th", "Where can the nightly ETL move?",
               "Can the checkout API move?", "Does robust optimisation pay?", "Is the forecast drifting?",
               "Present"]
DECISION_LINES = {
    "approve": "Approved and logged. Nothing was executed: this is a draft for the operations lead.",
    "reject": "Rejected and logged. The work stays where it was planned.",
}

# ------------------------------------------------------------------ speech


_MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
                "October", "November", "December"]
_ACRONYMS = [(r"\bA2A\b", "A to A"), (r"\bMCP\b", "M C P"), (r"\bETL\b", "E T L"), (r"\bCVaR\s?95\b", "C var 95"),
             (r"\bCVaR\b", "C var"), (r"\bRQ(\d)\b", r"R Q \1"), (r"S&OP", "S and O P"), (r"\bAPI\b", "A P I"),
             (r"\bDRO\b", "D R O"), (r"\bUTC\b", "U T C"), (r"\bCO2e?\b", "carbon"), (r"\bOWL RL\b", "owl R L"),
             (r"\bJSON-RPC\b", "JSON R P C"), (r"~", "about ")]


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def spoken_date(d: date) -> str:
    return f"{_MONTH_NAMES[d.month - 1]} {ordinal(d.day)}, {d.year}"


def month_name(ym: str) -> str:
    return _MONTH_NAMES[int(ym[5:7]) - 1]


def _no_dashes(text: str) -> str:
    return re.sub(r"\s*[\u2014\u2013]\s*", ", ", text)


def _round1(m: re.Match) -> str:
    v = round(float(m.group(1)), 1)
    return str(int(v)) if v == int(v) else str(v)


def to_tts(text: str) -> str:
    """The caption, rewritten so a voice reads it well."""
    t = _no_dashes(text)
    for zid in sorted(ZONE_NAMES, key=len, reverse=True):
        t = t.replace(zid, ZONE_NAMES[zid])
    t = re.sub(r"\b(20\d\d)-(\d\d)-(\d\d)\b", lambda m: spoken_date(date.fromisoformat(m.group(0))), t)
    t = re.sub(r"\b(20\d\d)-(\d\d)\b", lambda m: f"{month_name(m.group(0))} {m.group(1)}", t)
    t = t.replace("gCO2eq/kWh", "grams of carbon per kilowatt hour")
    t = re.sub(r"\bMWh\b", "megawatt hours", t)
    t = re.sub(r"\bkWh\b", "kilowatt hours", t)
    t = re.sub(r"(\d) t\b", r"\1 tonnes", t)
    t = re.sub(r"(\d%?)\s*-\s*(\d)", r"\1 to \2", t)
    t = re.sub(r"(?<![\d.])(\d+\.\d+)(?![\d.])(?!x\b)(?!\s*times\b)", _round1, t)
    t = re.sub(r"(\d+(?:\.\d+)?)x\b", r"\1 times", t)
    t = t.replace("%", " percent")
    for pat, rep in _ACRONYMS:
        t = re.sub(pat, rep, t)
    return re.sub(r"\s{2,}", " ", t).strip()


def speech(caption: str) -> dict:
    caption = _no_dashes(caption)
    return {"caption": caption, "tts": to_tts(caption)}


def _fmt(v: float) -> str:
    return f"{v:g}"


def _names(zones: list[str], limit: int = 2) -> str:
    names = [ZONE_NAMES.get(z, z) for z in zones]
    if len(names) <= limit:
        return " and ".join(names) if names else "nowhere"
    return f"{', '.join(names[:limit])} and {len(names) - limit} more"


LINES = {
    "greeting": "Hi, I'm Gridshift. Ask me to plan a job, or say present for the tour.",
    "listening_hint": "Hold space or tap the mic, then ask. For example: plan the model training for June 15th.",
    "mic_unavailable": "Speech input is not available in this browser, so please type your question instead.",
    "data_offline": "The licensed grid data is not on this machine, so live plans are off. "
                    "The thesis findings and the ontology still work.",
    "error": "Something went wrong on my side. Please try again.",
    "thinking": "One moment.",
    "ui": {
        "command": "Command view. The optimiser proposes, a person approves.",
        "knowledge": "Knowledge view. These are the rules the reasoner works from.",
        "evidence": "Evidence view. This is what the thesis found, out of sample.",
        "monitor": "Monitor view. This is how the forecast is holding up.",
        "interfaces": "Interfaces view. This is how other agents plug in.",
        "present_start": "Starting the three minute tour. Press Escape to stop.",
        "present_end": "That's the tour. Ask me anything.",
        "stopped": "Stopped.",
        "lens": "Here is the same problem in supply chain terms.",
    },
}


def lines() -> dict:
    return {k: ({kk: speech(vv) for kk, vv in v.items()} if isinstance(v, dict) else speech(v))
            for k, v in LINES.items()}


# ------------------------------------------------------------------ errors


class ApiError(Exception):
    status, code = 500, "internal"

    def __init__(self, message: str, caption: str | None = None):
        super().__init__(message)
        self.message = message
        self.caption = caption or message

    def body(self) -> dict:
        return {"error": {"code": self.code, "message": self.message, "speech": speech(self.caption)}}


class BadRequestError(ApiError):
    status, code = 400, "bad_request"


class NotFoundError(ApiError):
    status, code = 404, "not_found"


class OutOfRangeError(ApiError):
    status, code = 422, "out_of_range"


class DataUnavailableError(ApiError):
    status, code = 503, "data_unavailable"

    def __init__(self, message: str = "The licensed Electricity Maps data is not installed on this machine."):
        super().__init__(message, LINES["data_offline"])


class TTSUnavailableError(ApiError):
    status, code = 503, "tts_unavailable"


# ------------------------------------------------------------------ data guard


def _zone_years(zone: str) -> list[int]:
    if not DATA_DIR.is_dir():
        return []
    return sorted(int(m.group(1)) for f in DATA_DIR.glob(f"snapshots_*_{zone}-*-hourly.csv")
                  if (m := re.search(rf"_{re.escape(zone)}-(\d{{4}})-hourly\.csv$", f.name)))


def _zone_has_data(zone: str) -> bool:
    return 2025 in _zone_years(zone)


def data_available() -> bool:
    if os.environ.get("GRIDSHIFT_NO_DATA", "").strip() not in ("", "0"):
        return False
    return all(_zone_has_data(z["id"]) for z in ZONES)


def require_data() -> None:
    if not data_available():
        raise DataUnavailableError()


def day_range() -> dict:
    spans = [_zone_years(z["id"]) for z in ZONES]
    if all(spans):
        first, last = max(s[0] for s in spans), min(s[-1] for s in spans)
    else:
        first, last = 2021, 2025
    return {"first": (date(first, 1, 1) + timedelta(days=14)).isoformat(), "last": date(last, 12, 31).isoformat()}


def _parse_day(value) -> date:
    try:
        d = date.fromisoformat(str(value))
    except ValueError:
        raise BadRequestError(f"day must be YYYY-MM-DD, got {value!r}",
                         "I need the day as a date, for example June 15th, 2025.") from None
    r = day_range()
    if not r["first"] <= d.isoformat() <= r["last"]:
        raise OutOfRangeError(f"day {d} is outside the data ({r['first']} to {r['last']})",
                         f"I only have grid data from {r['first']} to {r['last']}.")
    return d


def _parse_share(value) -> float:
    try:
        s = float(value)
    except (TypeError, ValueError):
        raise BadRequestError(f"share must be a number, got {value!r}") from None
    if not 0 <= s <= 1:
        raise OutOfRangeError(f"share must be between 0 and 1, got {s}", "The transfer share must be between 0 and 100%.")
    return round(s, 4)


# ------------------------------------------------------------------ cache

# cached answers go stale when the code that builds them changes
_CODE = hashlib.sha1(b"".join((Path(__file__).parent / f).read_bytes() for f in
                              ("console.py", "scheduler.py", "workflow.py", "monitoring.py"))).hexdigest()[:12]
_MEM: dict[str, dict] = {}
_MEM_LOCK = threading.Lock()


def _cached(key: list, fn) -> tuple[dict, bool]:
    h = hashlib.sha1(json.dumps([CACHE_VERSION, _CODE, *key], sort_keys=True).encode()).hexdigest()
    with _MEM_LOCK:
        if h in _MEM:
            return copy.deepcopy(_MEM[h]), True
    path = API_CACHE / f"{h}.json"
    if path.is_file():
        try:
            val = json.loads(path.read_text(encoding="utf-8"))
            with _MEM_LOCK:
                _MEM[h] = val
            return copy.deepcopy(val), True
        except (OSError, ValueError):
            pass
    val = fn()
    with _MEM_LOCK:
        _MEM[h] = val
    try:
        API_CACHE.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{uuid.uuid4().hex[:8]}.tmp")
        tmp.write_text(json.dumps(val), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass
    return copy.deepcopy(val), False


# ------------------------------------------------------------------ ontology facts


@lru_cache(maxsize=1)
def _jobs() -> list[dict]:
    with SOLVER_LOCK:
        out = []
        for j in knowledge.jobs():
            o = knowledge.migration_options(j["job"])
            dc = knowledge._q(f"SELECT ?dc WHERE {{ :{j['job']} :runsAt ?dc }}")
            out.append({"job": j["job"], "label": j["label"], "flexible": j["flexible"],
                        "home_zone": o.get("home_zone"), "portfolio": o.get("portfolio"),
                        "allowed_zones": o["allowed_zones"],
                        "datacenter": knowledge._short(dc[0][0]) if dc else None})
        return out


@lru_cache(maxsize=1)
def _portfolios() -> list[dict]:
    from rdflib import RDFS, URIRef

    with SOLVER_LOCK:
        g = knowledge.graph(True)
        return [{"id": p, "label": str(g.value(URIRef(knowledge.NS + p), RDFS.label) or p),
                 "zones": knowledge.portfolio_zones(p)} for p in PORTFOLIOS]


def _job_info(job: str) -> dict | None:
    return next((j for j in _jobs() if j["job"] == job), None)


def _check_job(job: str) -> str:
    # job names go into SPARQL, so keep them to plain identifiers
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", str(job)):
        raise BadRequestError(f"bad job name {job!r}", "I don't know that job.")
    return str(job)


def _lower(label: str) -> str:
    # "Checkout API" -> "checkout API": keep acronyms
    return " ".join(w if w.isupper() and len(w) > 1 else w.lower() for w in label.split())


def _label(job: str) -> str:
    j = _job_info(job)
    return j["label"] if j else job


def _solver() -> str:
    try:
        from src.models.transfer_dro import _pick_solver
        return _pick_solver(None)
    except Exception:
        return "unknown"


# ------------------------------------------------------------------ endpoints


def health() -> dict:
    g0, g1 = knowledge.graph(False), knowledge.graph(True)
    return {"ok": True, "app": "Gridshift", "version": VERSION, "data_available": data_available(),
            "day_range": day_range(),
            "tts": {"available": bool(voice.engine()) or voice.cached_count() > 0, "engine": voice.engine_name(),
                    "voice": voice.voice(), "rate": voice.RATE, "pitch": voice.PITCH,
                    "cached_lines": voice.cached_count()},
            "solver": _solver(),
            "ontology": {"asserted_triples": len(g0), "reasoned_triples": len(g1)},
            "uptime_s": round(time.time() - START, 1)}


def meta() -> dict:
    has = data_available()
    ports = _portfolios()
    zones = [{**z, "portfolios": [p["id"] for p in ports if z["id"] in p["zones"]],
              "data": has and _zone_has_data(z["id"])} for z in ZONES]
    return {"app": {"name": "Gridshift", "tagline": "Carbon-aware workload console",
                    "thesis_title": "The Price of Sophistication", "subtitle": "IE capstone in Operations Research"},
            "default": dict(DEFAULT), "day_range": day_range(), "data_available": has,
            "carbon_scale": {"min": 0, "max": 800, "unit": "gCO2eq/kWh"},
            "zones": zones, "portfolios": ports, "jobs": _jobs(), "suggestions": SUGGESTIONS,
            "lens": LENS, "lines": lines()}


_STEP_META = [(1, "ontology", "Ontology check"), (2, "forecast", "Forecast"), (3, "plan", "Optimise"),
              (4, "explain", "Explain"), (5, "approval", "Human approval")]


def _plan_speech(p: dict) -> dict:
    status = p["status"]
    if status == "UNKNOWN_JOB":
        return speech("I don't know that job. Try the model training, the nightly data pipeline or the risk simulation.")
    if status == "NOT_MOVABLE":
        return speech(f"The {_lower(p['label'])} is user facing, so it stays in {_names([p['home_zone']])}. "
                      "Only flexible jobs move.")
    plan = p["plan"]
    net = plan["net_shift_mwh_by_zone"]
    losers = [z for z, v in sorted(net.items(), key=lambda kv: kv[1]) if v < 0]
    gainers = [z for z, v in sorted(net.items(), key=lambda kv: -kv[1]) if v > 0]
    if plan["moved_mwh"] <= 0 or plan["saving_pct"] <= 0:
        return speech(f"On {p['day']}, shifting hours alone would already have done the job: moving work would "
                      "have saved nothing extra. A one-day illustration, scored on what actually happened.")
    return speech(f"Moving {_fmt(plan['moved_mwh'])} MWh from {_names(losers)} to {_names(gainers)} would have cut "
                  f"that day's emissions by {_fmt(plan['saving_pct'])}% compared with shifting hours alone. "
                  "A one-day illustration, scored on what actually happened.")


def _headlines(status: str, info: dict | None, share: float, plan: dict | None) -> dict[int, str]:
    """One plain-English line per workflow step; the ontology detail stays in `lines`."""
    if status == "UNKNOWN_JOB":
        return {1: "Checked the rules: this job is not in the ontology, so I can't plan it"}
    if status == "NOT_MOVABLE":
        return {1: "Checked the rules: this job is user facing, so it stays where it is"}
    k = len((info or {}).get("allowed_zones", []))
    out = {1: f"Checked the rules: this job is allowed to move between these {k} regions",
           2: "Forecast each region's carbon, hour by hour, from the previous 14 days",
           3: f"Planned the day twice: shifting hours only, and also moving up to {_fmt(round(share * 100))}% "
              "of the work",
           5: "Waiting for the operations lead to sign off. Nothing has been executed"}
    if plan:
        out[4] = (f"Explained it: moving {_fmt(plan['moved_mwh'])} MWh would have cut that day's emissions by "
                  f"{_fmt(plan['saving_pct'])}% (a one-day illustration)")
    return out


def _build_plan(job: str, day: date, share: float) -> dict:
    from . import workflow

    with SOLVER_LOCK:
        w = workflow.propose(job, day, share, detail=True)
    raw = w["steps"]
    steps = []
    for (n, key, title), s in zip(_STEP_META, raw):
        res = s["result"]
        steps.append({"n": n, "key": key, "title": title, "lines": list(res) if isinstance(res, list) else [res]})
    info = _job_info(job)
    out = {"job": job, "label": _label(job), "status": w["status"], "day": day.isoformat(),
           "transfer_share": share, "home_zone": w.get("home_zone") or (info or {}).get("home_zone"),
           "steps": steps, "summary": w.get("summary"), "approval": None, "plan": None,
           "metric_definitions": w.get("metric_definitions"), "illustration": True}
    if w["status"] == "PENDING_APPROVAL":
        out["approval"] = {"required_from": w["approval_required_from"], "reason": w["approval_reason"],
                           "executed": False}
        out["plan"] = w["plan"]
    heads = _headlines(w["status"], info, share, out["plan"])
    for s in steps:
        s["headline"] = heads.get(s["n"], s["title"])
    out["speech"] = _plan_speech(out)
    return out


def plan(job: str | None = None, day=None, share=None) -> dict:
    t0 = time.perf_counter()
    job = _check_job(job or DEFAULT["job"])
    info = _job_info(job)
    share = _parse_share(DEFAULT["share"] if share is None else share)
    if info is None or not info["flexible"]:
        # nothing to optimise, so no licensed data needed
        out, hit = _build_plan(job, _parse_day(day or DEFAULT["day"]), share), False
    else:
        require_data()
        d = _parse_day(day or DEFAULT["day"])
        try:
            out, hit = _cached(["plan", job, d.isoformat(), share], lambda: _build_plan(job, d, share))
        except FileNotFoundError as e:
            raise DataUnavailableError(str(e)) from None
    out["cached"] = hit
    out["elapsed_ms"] = round((time.perf_counter() - t0) * 1000)
    return out


def sweep(job: str | None = None, day=None, shares=None) -> dict:
    t0 = time.perf_counter()
    job = _check_job(job or DEFAULT["job"])
    info = _job_info(job)
    if info is None:
        raise NotFoundError(f"unknown job {job!r}", "I don't know that job.")
    if not info["flexible"]:
        raise BadRequestError(f"{job} is not a flexible job, so there is nothing to sweep",
                         f"The {_lower(info['label'])} never moves, so there is no saving curve.")
    if shares is None:
        shares = [0, 0.1, 0.2, 0.3, 0.4, 0.5]
    elif isinstance(shares, str):
        shares = [s for s in shares.split(",") if s.strip()]
    shares = sorted({_parse_share(s) for s in shares})
    if not shares or len(shares) > 21:
        raise BadRequestError("give between 1 and 21 shares")
    require_data()
    d = _parse_day(day or DEFAULT["day"])
    points, all_hit, base = [], True, None
    for s in shares:
        p = plan(job, d.isoformat(), s)
        all_hit &= p["cached"]
        pl = p["plan"]
        base = pl["tonnes_time_shift_only"]
        points.append({"share": s, "transfer_budget_mwh": pl["transfer_budget_mwh"], "moved_mwh": pl["moved_mwh"],
                       "tonnes_with_migration": pl["tonnes_with_migration"], "saving_pct": pl["saving_pct"]})
    top = points[-1]
    cap = ("With no transfer budget, moving work saves nothing. " if points[0]["share"] == 0 else "") + \
          f"Allowing {_fmt(round(top['share'] * 100))}% of the work to move saves {_fmt(top['saving_pct'])}% that day."
    return {"job": job, "day": d.isoformat(), "tonnes_time_shift_only": base, "points": points,
            "speech": speech(cap), "cached": all_hit, "elapsed_ms": round((time.perf_counter() - t0) * 1000)}


def findings() -> dict:
    f = FIGURES
    cap = (f"Moving work between regions pays: {f['RQ1']['low_pct']:.1f} to {f['RQ1']['high_pct']:.1f}% lower "
           f"emissions on the worst days. Co-movement models add under {_fmt(f['RQ2']['max_gain_pct'])}%, and robust "
           f"hedging only pays at about {_fmt(f['RQ3']['breakeven_severity_x'])}x normal shocks.")
    return {"findings": dict(FINDINGS), "figures": copy.deepcopy(FIGURES), "ladder": copy.deepcopy(LADDER),
            "source": "Thesis results: out-of-sample CVaR95 over many days (results/).", "speech": speech(cap)}


@lru_cache(maxsize=1)
def _graph_export() -> dict:
    with SOLVER_LOCK:
        return knowledge.graph_export()


def graph() -> dict:
    out = copy.deepcopy(_graph_export())
    c = out["counts"]
    out["speech"] = speech(f"The reasoner grows {c['asserted_triples']} asserted facts into {c['reasoned_triples']}, "
                           "so nobody hand-codes which job may go where.")
    return out


def _build_drift(portfolio: str, start: date, end: date) -> dict:
    from . import monitoring

    ports = {p["id"]: p for p in _portfolios()}
    wanted = PORTFOLIOS if portfolio == "all" else [portfolio]
    out, alerts_total, closest = {}, 0, None
    for pid in wanted:
        rep = monitoring.drift_report(ports[pid]["zones"], start, end)
        zones = {}
        for z, info in rep["zones"].items():
            months = []
            for i, m in enumerate(info["months"]):
                base = i < rep["baseline_months"]
                months.append({**m, "baseline": base})
                if not base and (closest is None or m["ratio"] > closest["ratio"]):
                    closest = {"portfolio": pid, "zone": z, "zone_name": ZONE_NAMES.get(z, z),
                               "month": m["month"], "ratio": m["ratio"]}
            zones[z] = {"name": ZONE_NAMES.get(z, z), "baseline_mae": info["baseline_mae"], "months": months}
        alerts_total += len(rep["alerts"])
        out[pid] = {"label": ports[pid]["label"], "zones": zones, "alerts": rep["alerts"], "action": rep["action"]}
    res = {"period": f"{start} to {end}", "threshold": monitoring.THRESHOLD,
           "baseline_months": monitoring.BASELINE_MONTHS, "portfolios": out, "alerts_total": alerts_total,
           "closest": closest}
    res["speech"] = _drift_speech(res, start.year if start.year == end.year else None)
    return res


def _drift_speech(res: dict, year: int | None) -> dict:
    when = f"In {year}" if year else "Over this period"
    alerts = [a for p in res["portfolios"].values() for a in p["alerts"]]
    if alerts:
        worst = max(alerts, key=lambda a: a["ratio"])
        return speech(f"{when}, {len(alerts)} region months crossed the alarm. The worst was "
                      f"{ZONE_NAMES.get(worst['zone'], worst['zone'])} in {month_name(worst['month'])}, at "
                      f"{_fmt(worst['ratio'])}x, so I would re-check whether robust optimisation now pays there.")
    c = res["closest"]
    if not c:
        return speech(f"{when}, no region crossed the alarm.")
    return speech(f"{when}, no region crossed the alarm. The closest was {c['zone_name']} in "
                  f"{month_name(c['month'])}, at {_fmt(c['ratio'])}x.")


def drift(portfolio: str = "all", start=None, end=None) -> dict:
    portfolio = portfolio or "all"
    if portfolio != "all" and portfolio not in PORTFOLIOS:
        raise NotFoundError(f"unknown portfolio {portfolio!r}; use all, {', '.join(PORTFOLIOS)}")
    require_data()
    s = _parse_day(start or "2025-01-01")
    e = _parse_day(end or "2025-12-31")
    if e < s:
        raise BadRequestError("end is before start")
    try:
        out, hit = _cached(["drift", portfolio, s.isoformat(), e.isoformat()], lambda: _build_drift(portfolio, s, e))
    except FileNotFoundError as err:
        raise DataUnavailableError(str(err)) from None
    out["cached"] = hit
    return out


def evals() -> dict:
    from . import evals as ev

    require_data()   # two cases run the optimiser on the licensed data
    t0 = time.perf_counter()
    try:
        with SOLVER_LOCK:
            res = ev.run()
    except FileNotFoundError as err:
        raise DataUnavailableError(str(err)) from None
    passed = sum(r["routed"] and r["end_to_end"] for r in res["rows"])
    res["elapsed_ms"] = round((time.perf_counter() - t0) * 1000)
    res["speech"] = speech(f"{passed} out of {res['cases']} labelled requests route and answer correctly.")
    return res


@lru_cache(maxsize=1)
def _mcp_lists() -> dict:
    try:
        from . import mcp_server
    except Exception as e:  # mcp extra not installed
        return {"tools": [], "resources": [], "error": f"mcp not available: {type(e).__name__}"}
    tools = asyncio.run(mcp_server.server.list_tools())
    res = asyncio.run(mcp_server.server.list_resources())
    return {"tools": [{"name": t.name, "description": " ".join((t.description or "").split()),
                       "read_only": bool(t.annotations and t.annotations.read_only_hint),
                       "destructive": bool(t.annotations and t.annotations.destructive_hint)} for t in tools],
            "resources": [{"uri": str(r.uri), "name": r.name, "description": r.description,
                           "mime_type": r.mime_type} for r in res]}


def interfaces(base_url: str = "http://localhost:8765") -> dict:
    from . import a2a

    lists = copy.deepcopy(_mcp_lists())
    mcp = {"server": "carbon-aware-scheduler", "transport": "stdio", "run": "python -m agentic.mcp_server", **lists}
    ro = sum(t["read_only"] for t in mcp["tools"])
    card = a2a.agent_card(base_url)
    if mcp["tools"]:
        cap = (f"{len(mcp['tools'])} MCP tools, {ro} read only and {len(mcp['tools']) - ro} draft only, and an "
               f"A2A agent card with {len(card['skills'])} skills.")
    else:
        cap = f"An A2A agent card with {len(card['skills'])} skills. The MCP server is not installed here."
    return {"agent_card": card, "mcp": mcp,
            "a2a": {"endpoint": "/a2a", "card_url": "/.well-known/agent-card.json",
                    "protocol_version": a2a.PROTOCOL_VERSION},
            "speech": speech(cap)}


_AUDIT: deque = deque(maxlen=20)
_AUDIT_LOCK = threading.Lock()


def decide(body: dict) -> dict:
    if not isinstance(body, dict):
        raise BadRequestError("body must be a JSON object")
    decision = str(body.get("decision", "")).lower()
    if decision not in DECISION_LINES:
        raise BadRequestError("decision must be approve or reject")
    job = str(body.get("job") or DEFAULT["job"])
    if _job_info(job) is None:
        raise NotFoundError(f"unknown job {job!r}")
    share = _parse_share(body.get("share", DEFAULT["share"]))
    day = str(body.get("day") or DEFAULT["day"])
    if not re.fullmatch(r"\d{4}-\d\d-\d\d", day):
        raise BadRequestError("day must be YYYY-MM-DD")
    by = str(body.get("by") or "presenter")[:80]
    rec = {"id": str(uuid.uuid4()), "decision": decision,
           "status": "APPROVED_NOT_EXECUTED" if decision == "approve" else "REJECTED", "executed": False,
           "by": by, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "job": job, "day": day,
           "share": share}
    with _AUDIT_LOCK:
        _AUDIT.appendleft(rec)
        audit = [dict(a) for a in _AUDIT]
    return {**rec, "speech": speech(DECISION_LINES[decision]), "audit": audit}


# ------------------------------------------------------------------ ask

_DRIFT = re.compile(r"\b(drift|drifting|monitor|monitoring|forecast error|alarm|alerts?)\b")
_ABOUT = re.compile(r"\b(who are you|what are you|what is this|what can you do|help)\b")


def _error_reply(err: ApiError) -> tuple[None, dict, str]:
    return None, speech(err.caption), err.message


def ask(text: str, context: dict | None = None) -> dict:
    t0 = time.perf_counter()
    text = (text or "").strip()
    if not text:
        raise BadRequestError("text is empty", "I didn't catch that. Please try again.")
    if len(text) > 500:
        raise BadRequestError("text is too long")
    ctx = dict(context or {}) if isinstance(context, dict) else {}
    low = text.lower()
    if _DRIFT.search(low):
        intent, args = "drift", {"portfolio": "all"}
    elif _ABOUT.search(low):
        intent, args = "about", {}
    else:
        r = router.route(text)
        intent, args = r["intent"], dict(r["args"])
        if intent == "clarify" and router.has_explicit_day(text) and (router._job(text) or ctx.get("job")):
            intent = "propose_migration"
            args = {"job": router._job(text) or ctx["job"], "day": router._day(text).isoformat()}

    view, data, answer = None, None, ""
    try:
        if intent == "propose_migration":
            view = "command"
            data = plan(args["job"], args["day"], ctx.get("share", DEFAULT["share"]))
            sp = data["speech"]
            answer = data.get("summary") or sp["caption"]
            if data["plan"]:
                answer += " " + data["plan"]["note"]
            ctx.update(job=args["job"], day=args["day"])
        elif intent == "migration_options":
            view = "knowledge"
            with SOLVER_LOCK:
                data = knowledge.migration_options(args["job"])
            label = _label(args["job"])
            if data["flexible"]:
                z = data["allowed_zones"]
                sp = speech(f"The {_lower(label)} may move between {len(z)} regions: {_names(z)}. "
                            "The ontology works that out from where it runs.")
            else:
                sp = speech(f"The {_lower(label)} stays in {_names([data.get('home_zone')])}. "
                            "It is user facing, so it never moves.")
            answer = " ".join(data["why"])
            ctx["job"] = args["job"]
        elif intent == "findings":
            view = "evidence"
            data = findings()
            sp, answer = data["speech"], FINDINGS["recommendation"]
        elif intent == "metrics":
            view = "evidence"
            with SOLVER_LOCK:
                data = knowledge.metrics()
            sp = speech("Every number is defined once in the ontology. The one-day plans report emissions and "
                        "saving; the thesis reports CVaR95, the average over the worst 5% of days.")
            answer = " ".join(f"{v['label']} ({v['unit']}): {v['definition']}" for v in data.values())
        elif intent == "list_jobs":
            view = "command"
            js = _jobs()
            data = {"jobs": js}
            flex = [_lower(j["label"]) for j in js if j["flexible"]]
            fixed = [j["label"] for j in js if not j["flexible"]]
            sp = speech(f"There are {len(js)} jobs. {len(flex)} are flexible and can move; "
                        f"the {', '.join(_lower(f) for f in fixed)} is fixed.")
            answer = ", ".join(f"{j['label']} ({'flexible' if j['flexible'] else 'fixed'})" for j in js)
        elif intent == "drift":
            view = "monitor"
            data = drift("all")
            sp = data["speech"]
            answer = " ".join(p["action"] for p in data["portfolios"].values())
        elif intent == "about":
            sp = speech("I'm Gridshift. I plan where and when flexible computing runs, so it uses the cleanest "
                        "power, and a person approves every move.")
            answer = (sp["caption"] + " Try: " + "; ".join(SUGGESTIONS[:5]) + ".")
        else:
            data = {"known_jobs": [j["job"] for j in _jobs()], "suggestions": SUGGESTIONS}
            sp = speech("Which job, and what do you need? Try: plan the model training for June 15th.")
            answer = ("I can say where a job may move, propose a cleaner schedule for a day, summarise what the "
                      "thesis found, or check the forecast for drift.")
    except ApiError as err:
        data, sp, answer = _error_reply(err)
    return {"text": text, "intent": intent, "args": args, "view": view, "answer": answer, "speech": sp,
            "data": data, "context": ctx, "elapsed_ms": round((time.perf_counter() - t0) * 1000)}


# ------------------------------------------------------------------ present

PRESENT_QUERY = "Plan the nightly model training for June 15th"


def _try(fn):
    try:
        return fn()
    except Exception:
        return None


def _build_present() -> dict:
    has = data_available()
    g = graph()["counts"]
    allowed = (_job_info("llm_training") or {}).get("allowed_zones", [])
    f = FIGURES
    p = _try(lambda: plan("llm_training", DEFAULT["day"], DEFAULT["share"])) if has else None
    dr = _try(lambda: drift("all")) if has else None
    ev = _try(evals) if has else None

    s02 = ("This is Marco's capstone in operations research, turned into a working tool. Every number on screen is "
           f"computed live, from real hourly grid data for {len(ZONES)} North American regions.") if has else \
          ("This is Marco's capstone in operations research, turned into a working tool. With the licensed grid "
           "data installed, every number on screen is computed live.")
    if p and p.get("plan"):
        pl = p["plan"]
        s08 = (f"Moving {_fmt(pl['moved_mwh'])} megawatt hours, out of a budget of {_fmt(pl['transfer_budget_mwh'])}, "
               f"would have cut that day's emissions by {_fmt(pl['saving_pct'])} percent compared with shifting hours "
               "alone. That is a one-day illustration. The thesis tests this properly, out of sample, on the worst days.")
    else:
        s08 = "On this machine the licensed grid data is not installed, so I will skip the live plan."
    if dr and dr["alerts_total"]:
        alerts = [a for q in dr["portfolios"].values() for a in q["alerts"]]
        w = max(alerts, key=lambda a: a["ratio"])
        s14 = (f"It also watches itself. Every month it compares forecast error with a baseline. In 2025, "
               f"{len(alerts)} region months crossed the alarm. The worst was {ZONE_NAMES.get(w['zone'], w['zone'])} "
               f"in {month_name(w['month'])}, at {_fmt(w['ratio'])} times, so I would re-check whether robust "
               "optimisation now pays there.")
    elif dr and dr["closest"]:
        c = dr["closest"]
        s14 = ("It also watches itself. Every month it compares forecast error with a baseline. In 2025, no region "
               f"crossed the alarm. The closest was {c['zone_name']} in {month_name(c['month'])}, at "
               f"{_fmt(c['ratio'])} times.")
    else:
        s14 = ("It also watches itself. Every month it compares forecast error with a baseline. That check needs "
               "the licensed grid data, which is not installed here.")
    if ev:
        passed = sum(r["routed"] and r["end_to_end"] for r in ev["rows"])
        s15 = ("Other agents can use it too: tools over MCP, whole tasks over A2A. A labelled eval checks the "
               f"routing on every change. Right now: {passed} out of {ev['cases']}.")
    else:
        s15 = ("Other agents can use it too: tools over MCP, whole tasks over A2A. A labelled eval checks the "
               "routing on every change.")

    rows = [
        ("s01", "command", "boot", {}, None,
         "Hi, I'm Gridshift. I decide where and when a company's computing should run, so it runs on the cleanest "
         "power the grid has.", 2500),
        ("s02", "command", "focus_map", {}, "#map", s02, 2500),
        ("s03", "command", "show_lens", {}, "#lens",
         "Think of it as a supply chain for compute. Regions are the plants, flexible jobs are the orders, and "
         "carbon is a cost that changes every hour.", 2500),
        ("s04", "command", "type_query", {"text": PRESENT_QUERY}, "#dock",
         f"Let me ask it something real. {PRESENT_QUERY}.", 4000),
        ("s05", "command", "strip_step", {"n": 1}, "#strip",
         "First, it checks the rules. The ontology says training is flexible work, and the reasoner infers the "
         f"{len(allowed)} western regions it is allowed to use.", 2500),
        ("s06", "command", "strip_step", {"n": 3}, "#strip",
         "Then it forecasts each region's carbon, hour by hour, from the previous two weeks. The optimiser plans "
         "the day twice: once only shifting hours, once also moving work between regions.", 2500),
        ("s07", "command", "play_day", {}, "#map",
         "Here is the day playing out. Each dot is a grid region, coloured by how dirty its power is that hour, "
         "and work flows toward whoever is cleanest.", 6000),
        ("s08", "command", "show_kpis", {"n": 4}, "#kpis", s08, 2500),
        ("s09", "command", "gate_approve", {"n": 5}, "#gate",
         "And nothing moves on its own. Moving work changes where data is processed, so the operations lead signs "
         "it off. I log the approval, and still execute nothing.", 3000),
        ("s10", "evidence", "show_findings", {}, "#rq-cards",
         "So what did the thesis find? Moving work between regions pays: "
         f"{f['RQ1']['low_pct']:.1f} to {f['RQ1']['high_pct']:.1f} percent lower emissions on the worst days.", 2500),
        ("s11", "evidence", "show_rq3", {}, "#rq3",
         f"Modelling how regions move together adds less than {_fmt(f['RQ2']['max_gain_pct'])} percent. And robust "
         f"optimisation only pays when shocks are about {_fmt(f['RQ3']['breakeven_severity_x'])} times normal. "
         f"Real grids peaked at {_fmt(f['RQ3']['observed_severity_x'][1])} times.", 3000),
        ("s12", "evidence", "show_ladder", {}, "#ladder",
         "The value lesson: invest in the simple lever, the ability to move work, before buying sophistication. "
         "That is the price of sophistication.", 2500),
        ("s13", "knowledge", "run_reasoner", {}, "#kgraph",
         f"Under the hood, the rules live in an ontology. The reasoner grows {g['asserted_triples']} facts into "
         f"{g['reasoned_triples']}, so nobody hand-codes which job may go where.", 4000),
        ("s14", "monitor", "show_drift", {}, "#drift", s14, 3000),
        ("s15", "interfaces", "run_evals", {}, "#evals", s15, 3000),
        ("s16", "command", "close", {}, None,
         "Explainable, measured, and a person signs off every move. That's Gridshift. Ask me anything.", 2500),
    ]
    steps = [{"id": i, "view": v, "action": a, "args": args, "spotlight": spot, "speech": speech(cap), "min_ms": ms}
             for i, v, a, args, spot, cap, ms in rows]
    words = sum(len(s["speech"]["caption"].split()) for s in steps)
    # Ava at -6% reads about 2.35 words a second, plus the pauses between steps
    return {"title": "Gridshift in three minutes", "steps": steps, "total_words": words,
            "estimated_s": round(words / 2.35 + 0.6 * len(steps)), "data_available": has}


def present() -> dict:
    out, _ = _cached(["present", data_available()], _build_present)
    return out


def all_speech() -> list[str]:
    """Every fixed line the UI may speak without asking the server first."""
    out = []

    def walk(x):
        if isinstance(x, dict):
            if set(x) >= {"caption", "tts"} and isinstance(x["tts"], str):
                out.append(x["tts"])
            else:
                for v in x.values():
                    walk(v)
    walk(lines())
    walk({k: speech(v) for k, v in DECISION_LINES.items()})
    return out
