"""Routing: one plain-language request in, one tool out.

The routing pattern from "Building effective agents": classify the request, then hand it
to the specialist that handles that kind of request. Here the classifier is a few
transparent rules, not a model, because the request types are few and a wrong route
should be impossible to miss in a test. Swapping in an LLM classifier would only change
``route``; the tools behind it stay the same.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from . import knowledge

ALIASES = {
    "llm_training": ["training", "llm", "model training", "training run", "language model", "l l m"],
    "nightly_etl": ["etl", "pipeline", "nightly data", "e t l", "data pipeline"],
    "risk_batch": ["risk", "simulation", "risk batch"],
    "checkout_api": ["checkout", "api", "web", "check out"],
}
DEFAULT_DAY = date(2025, 6, 15)   # inside the frozen snapshot, so answers are reproducible


def _job(text: str) -> str | None:
    low = text.lower()
    for job in ALIASES:
        if job in low:
            return job
    for job, words in ALIASES.items():
        if any(re.search(rf"\b{re.escape(w)}\b", low) for w in words):
            return job
    return None


MONTHS = {m: i + 1 for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july",
                                          "august", "september", "october", "november", "december"])}
MONTHS.update({m[:3]: i for m, i in list(MONTHS.items())})
MONTHS["sept"] = 9
_ORD = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth",
        "eleventh", "twelfth", "thirteenth", "fourteenth", "fifteenth", "sixteenth", "seventeenth",
        "eighteenth", "nineteenth", "twentieth"]
ORDINALS = {w: i + 1 for i, w in enumerate(_ORD)}
ORDINALS.update({f"twenty {w}": 20 + i + 1 for i, w in enumerate(_ORD[:9])})
ORDINALS.update({"thirtieth": 30, "thirty first": 31})

_MON = "|".join(sorted(MONTHS, key=len, reverse=True))
_ORDW = "|".join(sorted((w.replace(" ", r"[\s-]") for w in ORDINALS), key=len, reverse=True))
_DAYN = rf"(\d{{1,2}})(?:st|nd|rd|th)?\b|({_ORDW})\b"
_YEAR = r"(?:,?\s*(20\d\d)\b)?"
_MONTH_DAY = re.compile(rf"\b({_MON})\b\.?,?\s+(?:the\s+)?(?:{_DAYN}){_YEAR}")
_DAY_MONTH = re.compile(rf"\b(?:the\s+)?(?:{_DAYN})(?:\s+of)?\s+({_MON})\b\.?{_YEAR}")


def _make(year, month, day) -> date | None:
    try:
        return date(int(year) if year else DEFAULT_DAY.year, month, day)
    except ValueError:
        return None


def _num(digits, word) -> int:
    return int(digits) if digits else ORDINALS[re.sub(r"[\s-]+", " ", word)]


def _named_day(low: str) -> tuple[bool, date | None]:
    """(found, day) for "June 15th", "Jun. 3rd, 2023", "15th of June 2024", "June fifteenth"."""
    m = _MONTH_DAY.search(low)
    if m:
        return True, _make(m.group(4), MONTHS[m.group(1)], _num(m.group(2), m.group(3)))
    m = _DAY_MONTH.search(low)
    # "may" is also a verb, so "5 may" only counts with a year after it
    if m and (m.group(3) != "may" or m.group(4)):
        return True, _make(m.group(4), MONTHS[m.group(3)], _num(m.group(1), m.group(2)))
    return False, None


def _relative(low: str) -> date | None:
    if re.search(r"\btoday\b", low):
        return DEFAULT_DAY
    if re.search(r"\byesterday\b", low):
        return DEFAULT_DAY - timedelta(days=1)
    if "tomorrow" in low:
        return DEFAULT_DAY + timedelta(days=1)
    return None


def _day(text: str) -> date:
    m = re.search(r"(20\d\d-\d\d-\d\d)", text)
    if m:
        return date.fromisoformat(m.group(1))
    low = text.lower()
    found, d = _named_day(low)
    if found:
        return d or DEFAULT_DAY   # Feb 30 and friends fall back to the default
    return _relative(low) or DEFAULT_DAY


def has_explicit_day(text: str) -> bool:
    low = text.lower()
    return bool(re.search(r"20\d\d-\d\d-\d\d", text)) or _named_day(low)[0] or _relative(low) is not None


def route(text: str) -> dict:
    """{intent, args}: which tool should answer, with what."""
    low = text.lower()
    job = _job(text)
    if re.search(r"\b(metric|define|definition|what does .* mean|cvar)\b", low):
        return {"intent": "metrics", "args": {}}
    if re.search(r"\b(finding|findings|thesis|result|does .* pay|robust|dro|copula|covariance)\b", low):
        return {"intent": "findings", "args": {}}
    if job and re.search(r"\b(plan|propose|schedule|move it|shift|save|saving|run it)\b", low):
        return {"intent": "propose_migration", "args": {"job": job, "day": _day(text).isoformat()}}
    if job and re.search(r"\b(where|can|allowed|may|movable|move)\b", low):
        return {"intent": "migration_options", "args": {"job": job}}
    if re.search(r"\b(jobs|list|what runs|workloads)\b", low):
        return {"intent": "list_jobs", "args": {}}
    return {"intent": "clarify", "args": {"known_jobs": [j["job"] for j in knowledge.jobs()]}}
