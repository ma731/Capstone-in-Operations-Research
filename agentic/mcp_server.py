"""The carbon-aware scheduler as an MCP server: any agent can ask; nothing it asks moves work.

    python -m agentic.mcp_server        # stdio

Tools are read-only except ``propose_migration``, which returns a draft that a person
must approve. The ontology and the thesis findings are exposed as resources, so an agent
can read the rules and the evidence before it proposes anything.
"""
from __future__ import annotations

import json
from datetime import date

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from . import knowledge, workflow
from .findings import FINDINGS

READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
DRAFT_ONLY = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)

server = MCPServer(
    "carbon-aware-scheduler",
    instructions=(
        "Day-ahead carbon-aware scheduling for data centres (IE capstone, Prof. Bissan Ghaddar). "
        "Read capstone://ontology to see which jobs may move and where. propose_migration returns a "
        "draft only: a person approves every cross-region move. Read capstone://findings before "
        "suggesting robust optimisation or richer dependence models: the thesis finds they rarely pay."
    ),
)


@server.tool(annotations=READ_ONLY)
def list_jobs() -> list[dict]:
    """Every job in the ontology, and whether the reasoner classifies it as flexible."""
    return knowledge.jobs()


@server.tool(annotations=READ_ONLY)
def migration_options(job: str) -> dict:
    """Whether a job may move between regions, which regions, and the chain of facts behind it."""
    return knowledge.migration_options(job)


@server.tool(annotations=DRAFT_ONLY)
def propose_migration(job: str, day: str, transfer_share: float = 0.3) -> dict:
    """Draft a one-day migration plan for a flexible job (day as YYYY-MM-DD, 2021-2025 data).
    Compares time shifting only with moving up to transfer_share of the work between the regions
    the ontology allows, scored on the carbon that actually happened. Never executes: the result
    is PENDING_APPROVAL for a person."""
    return workflow.propose(job, date.fromisoformat(day), transfer_share=transfer_share)


@server.resource("capstone://ontology", name="ontology",
                 description="Classes, relations, property chains and the portfolios, as Turtle (RDFS + OWL).",
                 mime_type="text/turtle")
def ontology_resource() -> str:
    return knowledge.ONTOLOGY.read_text(encoding="utf-8")


@server.resource("capstone://metrics", name="metrics",
                 description="The semantic layer: every reported metric, defined once in the ontology.",
                 mime_type="application/json")
def metrics_resource() -> str:
    return json.dumps(knowledge.metrics(), indent=2)


@server.resource("capstone://findings", name="findings",
                 description="What the thesis found: which layer of sophistication pays.",
                 mime_type="application/json")
def findings_resource() -> str:
    return json.dumps(FINDINGS, indent=2)


if __name__ == "__main__":
    server.run("stdio")
