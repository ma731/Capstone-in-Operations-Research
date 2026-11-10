"""The scheduler as an A2A agent: another company's agent can find it and delegate a task.

MCP (mcp_server.py) lets an agent use this project's TOOLS. A2A, the Agent2Agent
protocol, is the other direction: a peer agent hands over a whole TASK in plain language
and gets a result, without knowing what runs inside.

    agent_card(base_url)   the Agent Card, served at /.well-known/agent-card.json
    handle(payload)        JSON-RPC 2.0 "message/send": router -> tool -> A2A Task

A request the router cannot place comes back ``input-required`` with what it can do,
which is A2A's way of asking a question back. Nothing here moves work: a proposal is
returned as a draft pending a person.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from . import knowledge, router, workflow
from .findings import FINDINGS

PROTOCOL_VERSION = "0.3.0"
SKILLS = [
    {"id": "migration_options", "name": "Where can a job run?",
     "description": "Whether a compute job may move between regions, and where, with the ontology's reasons.",
     "tags": ["carbon", "scheduling", "ontology"], "examples": ["Where can the nightly ETL pipeline move?"]},
    {"id": "propose_migration", "name": "Propose a cleaner schedule",
     "description": "A one-day plan moving flexible work to cleaner regions and hours. A draft pending approval.",
     "tags": ["carbon", "optimisation"], "examples": ["Plan the model training for 2025-06-15"]},
    {"id": "findings", "name": "What pays?",
     "description": "What the thesis found about migration, co-movement and robust optimisation.",
     "tags": ["research"], "examples": ["Does robust optimisation pay?"]},
]


def agent_card(base_url: str) -> dict:
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "name": "Carbon-aware scheduler",
        "description": ("Day-ahead carbon-aware scheduling for data centres (IE capstone). Says which jobs may "
                        "move and drafts cleaner schedules; never moves work without a person."),
        "url": base_url.rstrip("/") + "/a2a",
        "preferredTransport": "JSONRPC",
        "version": "1.0.0",
        "capabilities": {"streaming": False, "pushNotifications": False},
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain", "application/json"],
        "skills": SKILLS,
    }


def _task(context_id, state, text, data=None):
    tid = str(uuid.uuid4())
    task = {"kind": "task", "id": tid, "contextId": context_id,
            "status": {"state": state, "timestamp": datetime.now(timezone.utc).isoformat(),
                       "message": {"kind": "message", "role": "agent", "messageId": str(uuid.uuid4()),
                                   "parts": [{"kind": "text", "text": text}], "taskId": tid, "contextId": context_id}}}
    if state == "completed":
        parts = [{"kind": "text", "text": text}] + ([{"kind": "data", "data": data}] if data is not None else [])
        task["artifacts"] = [{"artifactId": str(uuid.uuid4()), "name": "result", "parts": parts}]
    return task


def answer(text: str) -> tuple[str, str, dict | None]:
    """(state, text, data) for one plain-language request."""
    r = router.route(text)
    intent, args = r["intent"], r["args"]
    if intent == "migration_options":
        o = knowledge.migration_options(args["job"])
        msg = (f"{args['job']} may move between {', '.join(o['allowed_zones'])}." if o["flexible"]
               else f"{args['job']} stays in {o.get('home_zone')}: it is not a flexible job.")
        return "completed", msg, o
    if intent == "propose_migration":
        p = workflow.propose(args["job"], date.fromisoformat(args["day"]))
        return "completed", p.get("summary") or f"{args['job']}: {p['status']}", p
    if intent == "findings":
        return "completed", FINDINGS["recommendation"], FINDINGS
    if intent == "metrics":
        return "completed", "Every metric, defined once.", knowledge.metrics()
    if intent == "list_jobs":
        js = knowledge.jobs()
        return "completed", ", ".join(f"{j['job']} ({'flexible' if j['flexible'] else 'fixed'})" for j in js), {"jobs": js}
    return "input-required", ("Which job, and what do you need? I can say where a job may move, propose a cleaner "
                              "schedule for a day, or summarise what the thesis found. Jobs: "
                              + ", ".join(args["known_jobs"]) + "."), None


def handle(payload: dict) -> dict:
    req_id = payload.get("id") if isinstance(payload, dict) else None
    if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0":
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32600, "message": "Invalid Request"}}
    if payload.get("method") != "message/send":
        return {"jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {payload.get('method')}"}}
    msg = (payload.get("params") or {}).get("message") or {}
    text = " ".join(p.get("text", "") for p in msg.get("parts") or [] if p.get("kind") == "text").strip()
    if not text:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": "message.parts needs text"}}
    state, out, data = answer(text)
    return {"jsonrpc": "2.0", "id": req_id, "result": _task(msg.get("contextId") or str(uuid.uuid4()), state, out, data)}
