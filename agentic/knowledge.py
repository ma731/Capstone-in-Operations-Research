"""The ontology, reasoned over: which jobs may move, and where.

The graph is loaded from ``ontology.ttl`` and expanded with an OWL RL reasoner, so
facts that follow from the schema are added rather than written by hand:

* subclass (RDFS): a TrainingJob is a FlexibleJob, so it is a Job;
* domain (RDFS): anything ``locatedIn`` a region is a DataCenter;
* property chains (OWL 2): ``runsAt`` then ``memberOf`` then ``hasRegion`` gives the
  regions a job's work could move to.

The scheduler never decides what is allowed to move. The ontology does; the
optimisation only decides how much, when and where among the allowed regions.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

ONTOLOGY = Path(__file__).with_name("ontology.ttl")
NS = "https://github.com/ma731/Capstone-in-Operations-Research/ontology#"


def _short(uri) -> str:
    return str(uri).rsplit("#", 1)[-1]


@lru_cache(maxsize=2)
def graph(reason: bool = True):
    """The ontology as an rdflib Graph, with inferred triples when ``reason`` is True."""
    import rdflib

    g = rdflib.Graph()
    g.parse(ONTOLOGY, format="turtle")
    if reason:
        import owlrl

        owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(g)
    return g


def _q(query: str, reason: bool = True):
    return list(graph(reason).query("PREFIX : <" + NS + ">\n"
                                    "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n" + query))


def types_of(name: str, reason: bool = True) -> list[str]:
    """Every ontology class an individual belongs to (asserted, plus inferred if reasoning)."""
    rows = _q(f"SELECT DISTINCT ?c WHERE {{ :{name} a ?c . FILTER(STRSTARTS(STR(?c), '{NS}')) }}", reason)
    return sorted(_short(r[0]) for r in rows)


def jobs() -> list[dict]:
    rows = _q("SELECT ?j ?label WHERE { ?j a :Job ; rdfs:label ?label }")
    out = [{"job": _short(j), "label": str(label), "flexible": "FlexibleJob" in types_of(_short(j))}
           for j, label in rows]
    return sorted(out, key=lambda r: r["job"])


def portfolio_zones(portfolio: str) -> list[str]:
    rows = _q(f"SELECT ?z WHERE {{ ?r :inPortfolio :{portfolio} ; :zoneId ?z }}")
    return sorted(str(r[0]) for r in rows)


def metrics() -> dict:
    """The semantic layer: every reported metric, defined once in the ontology. Risk
    metrics are found by subclass inference (a RiskMetric is a Metric)."""
    rows = _q("SELECT ?m ?label ?unit ?def ?use WHERE { ?m a :Metric ; rdfs:label ?label ; :unit ?unit ; "
              ":definition ?def ; :usedFor ?use }")
    risk = {_short(r[0]) for r in _q("SELECT ?m WHERE { ?m a :RiskMetric }")}
    return {_short(m): {"label": str(lb), "unit": str(u), "definition": str(d), "used_for": str(us),
                        "risk_metric": _short(m) in risk} for m, lb, u, d, us in rows}


def migration_options(job: str) -> dict:
    """Whether a job may move, where to, and the chain of facts that says so."""
    kinds = types_of(job)
    if not kinds:
        return {"job": job, "known": False, "flexible": False, "allowed_zones": [],
                "why": [f"'{job}' is not in the ontology."]}
    asserted = types_of(job, reason=False)
    home = _q(f"SELECT ?z ?dc ?p WHERE {{ :{job} :homeRegion ?r ; :runsAt ?dc . ?r :zoneId ?z . "
              f"?dc :memberOf ?p }}")
    home_zone, dc, portfolio = (str(home[0][0]), _short(home[0][1]), _short(home[0][2])) if home else (None, None, None)
    flexible = "FlexibleJob" in kinds
    why = [f"{job} is asserted as {', '.join(asserted)}; the reasoner adds {', '.join(k for k in kinds if k not in asserted) or 'nothing'} (rdfs:subClassOf)."]
    if dc:
        why.append(f"It runs at {dc}, which the reasoner types as "
                   f"{', '.join(types_of(dc))} from rdfs:domain, in portfolio {portfolio}.")
    if not flexible:
        why.append("It is not a FlexibleJob (FixedJob is disjoint with FlexibleJob), so it stays where it is.")
        return {"job": job, "known": True, "flexible": False, "home_zone": home_zone, "portfolio": portfolio,
                "allowed_zones": [home_zone] if home_zone else [], "why": why}
    zones = sorted(str(r[0]) for r in _q(f"SELECT ?z WHERE {{ :{job} :reachableRegion ?r . ?r :zoneId ?z }}"))
    why.append(f"reachableRegion is inferred by the property chain runsAt → memberOf → hasRegion: {', '.join(zones)}.")
    return {"job": job, "known": True, "flexible": True, "home_zone": home_zone, "portfolio": portfolio,
            "allowed_zones": zones, "why": why}
