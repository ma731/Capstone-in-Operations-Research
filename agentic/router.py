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
    "llm_training": ["training", "llm", "model training"],
    "nightly_etl": ["etl", "pipeline", "nightly data"],
    "risk_batch": ["risk", "simulation", "risk batch"],
    "checkout_api": ["checkout", "api", "web"],
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


def _day(text: str) -> date:
    m = re.search(r"(20\d\d-\d\d-\d\d)", text)
    if m:
        return date.fromisoformat(m.group(1))
    if "tomorrow" in text.lower():
        return DEFAULT_DAY + timedelta(days=1)
    return DEFAULT_DAY


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
