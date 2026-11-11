"""Offline answers to the questions people ask about the capstone.

No model: a small scorer over stemmed keywords and example questions, so paraphrases land
on the right topic. Every number is copied from a file in the repo, named in `src`, and
tests/test_voice_faq.py re-reads the snapshot CSVs to keep them honest.
"""
from __future__ import annotations

import re

SNAP = "docs/results_snapshots/"

# ------------------------------------------------------------------ text


_STOP = set("""a an the is are was were be been do does did of to in on for and or with by it its this that
these those i you we me my your our us can could would should will shall may might must about how what why
which whom when where there here tell me please explain describe give say so just really any some
also than then them they he she his her have has had not no yes if as at from into over under more most
very much many get got let lets show walk through quick quickly brief briefly one bit doesn don isn didn t s take
""".split())

# spoken or typed variants folded into one token before matching
_SYNONYMS = [
    (r"\bd\s?r\s?o\b|\bdistributionally robust( optimi[sz]ation)?\b", " dro "),
    (r"\bvalue of (the )?stochastic solution\b|\bvss\b", " vss "),
    (r"\bstochastic program(ming|me|s)?\b|\bsample average( approximation)?\b|\bsaa\b", " stochprog "),
    (r"\bclassic(al)? robust( optimi[sz]ation)?\b|\brobust counterpart\b|\buncertainty set\b|\bworst case set\b",
     " robustopt "),
    (r"\bc\s?var\b|\bconditional value at risk\b", " cvar "),
    (r"\bm\s?c\s?p\b|\bmodel context protocol\b", " mcp "),
    (r"\ba\s?(2|to|two)\s?a\b|\bagent to agent\b", " a2a "),
    (r"\bfeasible (set|region)\b|\bconstraint set\b", " feasibleset "),
    (r"\bambiguity (set|ball)\b|\bwasserstein( ball)?\b", " ambiguity "),
    (r"\bnull (result|finding)\b|\bnegative result\b|\bnothing found\b|\bfound nothing\b", " null "),
    (r"\bco ?movement\b|\bcorrelat\w*\b|\bcovariance\b|\bdependence\b|\bmove together\b", " correlation "),
    (r"\bmigrat\w*\b|\bmoving work\b|\bmove work\b|\bshift\w* (work|load|jobs?) between\b|\btransfer\w*\b",
     " migration "),
    (r"\bknowledge graph\b|\bowl\b|\brdf\w*\b|\breasoner\b", " ontology "),
    (r"\bco2\w*\b|\bemissions?\b|\bgreenhouse\b", " carbon "),
    (r"\bspeech\b|\btext to speech\b|\btts\b|\btalk\w*\b|\bspeak\w*\b", " voice "),
    (r"\bllm\b|\bchat ?gpt\b|\blanguage model\b|\bgpt\b|\bclaude\b", " llm "),
    (r"\bnext steps?\b|\bfuture work\b|\bwhat next\b|\bwith more time\b|\bfollow ups?\b|\bextend\w*\b", " future "),
    (r"\bweak(ness|nesses)?\b|\bcaveats?\b|\bshortcomings?\b|\blimit(s|ations?)\b|\bdrawbacks?\b", " limitation "),
    (r"\bspin up\b|\bstart up\b|\blaunch\b|\bset up\b|\bsetup\b|\binstall\b", " run "),
    (r"\bhuman in the loop\b|\bsign(s|ed)? off\b|\bapprov\w*\b", " approval "),
    (r"\bbase ?lines?\b|\bbenchmarks?\b|\bcompared? (it )?(to|with|against)\b|\bcomparison\b", " baseline "),
]


def _stem(w: str) -> str:
    if w.endswith(("ss", "is", "us", "ys")):
        return w
    for suf, rep in (("ies", "y"), ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + rep
    return w


def normalize(text: str) -> str:
    t = " " + re.sub(r"[^a-z0-9]+", " ", text.lower()) + " "
    for pat, rep in _SYNONYMS:
        t = re.sub(pat, rep, t)
    return re.sub(r"\s+", " ", t).strip()


def tokens(text: str) -> set[str]:
    return {_stem(w) for w in normalize(text).split() if w not in _STOP}


# ------------------------------------------------------------------ topics
# key: id; title: for the help list; kw: stem -> weight; ex: example questions;
# need: regex the raw lowercase text must match (for topics that would otherwise steal);
# say: the spoken answer (2 to 4 sentences); more: extra text for the reply panel;
# src: where the numbers come from; view: the console view to open, if any.

TOPICS: list[dict] = [
    # ---------------------------------------------------------- the project
    dict(key="overview", title="the project in one breath", view=None,
         kw={"capstone": 2, "thesis": 1.5, "project": 1.5, "summary": 2, "summar": 2, "elevator": 3, "pitch": 2,
             "overview": 2, "about": 0.5, "nutshell": 3, "sum": 1.5, "problem": 2, "solv": 1},
         need=r"capstone|thesis about|project|summar|elevator|pitch|overview|nutshell|sum (it )?up|in one (sentence|"
              r"breath)|what did you study|what is (the|this|your) thesis|problem",
         ex=["what is the capstone about", "summarise the thesis", "give me the elevator pitch",
             "what is your project", "explain the project in one sentence", "what did you study"],
         say="The capstone asks how sophisticated a carbon-aware data centre scheduler needs to be. It prices three "
             "optional layers one at a time: moving work between regions, modelling how regions' carbon moves "
             "together, and hedging forecast error with distributionally robust optimisation. One layer pays and "
             "two mostly do not, which is why the title is The Price of Sophistication.",
         src="README.md (In one paragraph)"),
    dict(key="research_questions", title="the three research questions", view="evidence",
         kw={"research": 1.5, "question": 1.5, "rq": 2, "rq1": 1, "rq2": 1, "rq3": 1, "hypothes": 2, "aim": 1.5},
         ex=["what are the research questions", "what were you trying to answer", "what are rq1 rq2 and rq3",
             "what is the hypothesis", "what are the aims of the thesis"],
         say="There are three. RQ1: does letting jobs move between regions cut worst-day emissions? RQ2: does "
             "modelling how regions co-move improve the schedule? RQ3: does hedging forecast error with DRO pay, "
             "and do real grids reach the conditions where it would?",
         src="README.md (Research questions at a glance)"),
    dict(key="who", title="who built it", view=None,
         kw={"supervis": 3, "advis": 3, "who": 1.5, "author": 2, "built": 1, "made": 1, "creat": 1, "ghaddar": 3,
             "marco": 2, "universit": 2, "school": 1.5, "ie": 1},
         need=r"supervis|advis|author|built|made|creat|who (is|was) (the|your)|universit|school|ghaddar|marco",
         ex=["who supervised this", "who built this project", "who is the author", "which university is this from",
             "who was your advisor"],
         say="Marco Ortiz Togashi built it as his research capstone in Operations Research at IE School of Science "
             "and Technology in 2026. Professor Bissan Ghaddar supervised it. Gridshift, this console, is a "
             "post-capstone extension over the same code.",
         src="README.md (header)"),
    dict(key="contribution", title="what is new compared with prior work", view=None,
         kw={"new": 1.5, "novel": 3, "novelty": 3, "contribution": 3, "contribut": 3, "prior": 2, "literature": 2,
             "hall": 3, "differ": 1.5, "original": 2},
         ex=["what is new here", "what is your contribution", "how is this different from prior work",
             "how does this compare to hall et al", "what is novel about it"],
         say="Hall and colleagues, 2024, apply Wasserstein DRO to carbon-aware scheduling one region at a time. "
             "This work extends it to the joint, correlated carbon field across regions, and then measures what "
             "each extra layer actually buys against a like-for-like baseline. Migration itself is established "
             "practice; the contribution is the honest measurement of its value and the two pre-committed nulls.",
         src="thesis/capstone_thesis.tex (Relation to prior work); README.md (The finding)"),
    # ---------------------------------------------------------- method
    dict(key="method", title="how the model works", view=None,
         kw={"method": 2, "methodology": 2, "model": 1, "formulation": 2.5, "objective": 2, "algorithm": 2,
             "optimi": 1, "spatial": 1.5, "work": 0.3, "dro": 1},
         ex=["how does the model work", "explain the method", "what is spatial correlation dro",
             "walk me through the formulation", "what is the objective function", "what does the optimiser do"],
         say="Each day the scheduler decides how much compute to run in each region and hour. It minimises the "
             "expected carbon plus a penalty, epsilon times the square root of x transpose sigma x, where sigma is "
             "the covariance of forecast error across all regions and hours. The off-diagonal blocks of sigma are "
             "the spatial channel, and the whole thing solves as a second-order cone program.",
         src="README.md (Method); thesis/full_formulation.md"),
    dict(key="ambiguity_set", title="the ambiguity set", view=None,
         kw={"ambiguity": 3, "ball": 1.5, "mahalanobis": 3, "uncertain": 2, "metric": 0.5, "distribution": 1},
         ex=["what is the ambiguity set", "what is the wasserstein ball", "how is uncertainty modelled",
             "what does the mahalanobis distance do", "what distributions do you hedge against"],
         say="It is a type-2 Wasserstein ball of radius epsilon around the empirical distribution of day-ahead "
             "forecast error, pooled over 2021 to 2024. The distance uses a Mahalanobis metric from the residual "
             "covariance, so correlated regions count as closer. For a linear cost the worst case collapses to "
             "the mean plus epsilon times the square root of x transpose sigma x.",
         src="thesis/capstone_thesis.tex (Distributionally robust formulation)"),
    dict(key="epsilon", title="how the radius epsilon is chosen", view=None,
         kw={"epsilon": 3, "radius": 2.5, "tun": 1.5, "cross": 1, "validation": 2, "valid": 1, "hyperparameter": 2,
             "choose": 1, "chose": 1, "select": 1, "pick": 1},
         need=r"epsilon|radius|\btun(e|ed|ing)\b|cross.?valid|hyperparam|"
              r"(choos|chose|pick|select)\w* .*(epsilon|radius|ball|size)", boost=1.5,
         ex=["how do you choose epsilon", "how is the radius picked", "how did you tune the ball size",
             "is epsilon cross validated"],
         say="Epsilon is picked by blocked five-fold cross-validation on the training years only. It selects an "
             "interior radius, so the robust layer genuinely engages; very large epsilon is over-conservative. "
             "The test year, 2025, is read once after the choice is locked.",
         src="thesis/capstone_thesis.tex (CV figure caption, Algorithm 1)"),
    dict(key="feasible_set", title="the feasible set and constraints", view=None,
         kw={"feasibleset": 3, "constraint": 2.5, "ramp": 2, "deadline": 2, "capacity": 1.5, "pue": 2,
             "thermal": 2, "inflexible": 2, "flexible": 1, "polytope": 2},
         ex=["what constraints does the scheduler have", "what is the feasible set", "what limits the schedule",
             "explain the ramp and deadline constraints"],
         say="Every scheduler shares one feasible set, so any difference comes from the objective alone. It has a "
             "per-cell capacity ceiling, an inflexible share of each region's work on a fixed shape, a ramp limit "
             "between hours, a deadline on part of the flexible work, and a thermal limit where cooling, through "
             "PUE, tightens capacity in hot hours.",
         src="src/models/feasible_set.py; thesis/full_formulation.md"),
    dict(key="feasible_revision", title="why the feasible set was revised", view=None,
         kw={"revis": 3, "revised": 3, "cap": 2, "drop": 2, "dropped": 2, "remov": 1.5, "chang": 1,
             "feasibleset": 1.5, "mechanical": 2, "artifact": 2, "artefact": 2, "frozen": 2, "task": 1},
         need=r"revis|cap\b|drop|remov|chang|artifact|artefact|frozen|mechanical|task a",
         ex=["why was the feasible set revised", "why did you drop the power cap",
             "is the null just an artefact of the constraints", "was the schedule frozen by the constraints",
             "what changed in task a"],
         say="The first version had an aggregate hourly power cap of 180 that pinned the schedule to a flat face of "
             "the polytope, so it barely moved. Task A dropped the cap and added a deadline and a temperature-driven "
             "cooling limit, which are more realistic. The null was re-confirmed on the new set, gaps under 0.06% in "
             "all nine cells, while the robust schedule still reallocated about 25 to 30% of the work, so it is "
             "substantive, not frozen.",
         src="thesis/constraints_explained.md; thesis/full_formulation.md; " + SNAP + "taskA_regimes_2026-06-02.csv"),
    dict(key="why_dro", title="why DRO rather than stochastic programming or robust optimisation", view=None,
         kw={"stochprog": 3, "robustopt": 3, "why": 0.5, "instead": 1.5, "rather": 1.5, "choice": 1, "chose": 1,
             "dro": 1.5, "alternative": 1.5},
         need=r"stochastic(?! solution)|sample average|\bsaa\b|classic(al)? robust|robust counterpart|uncertainty set|"
              r"(instead of|rather than|versus|\bvs\b|why not|alternatives?)\b.*(\bd ?r ?o\b|distributionally|robust "
              r"optimi|stochastic)|why (use|choose|chose|pick|did you (use|choose|pick)) (d ?r ?o\b|distributionally)",
         boost=3,
         ex=["why dro and not stochastic programming", "why not robust optimisation",
             "why distributionally robust instead of sample average approximation", "why did you choose dro",
             "what are the alternatives to dro"],
         say="Stochastic programming trusts the sample exactly, and classic robust optimisation ignores the data "
             "and is very conservative. Wasserstein DRO sits in between with one dial, epsilon: zero is the plain "
             "data-driven plan, larger is more cautious, and for linear costs it stays a fast cone program. It also "
             "extends Hall et al. directly, and the stochastic route was tested too: the copula schedulers are CVaR "
             "sample-average programs, and they found nothing either.",
         src="thesis/capstone_thesis.tex (sections 2 and 3, Appendix copula); README.md (Method)"),
    dict(key="why_cvar", title="why CVaR and not the average", view="evidence",
         kw={"cvar": 1.5, "worst": 1.5, "tail": 1.5, "average": 1, "mean": 1, "why": 0.5, "risk": 1},
         need=r"why|instead|rather|not the (mean|average)|tail level|0\.9|0\.99|worst day",
         ex=["why cvar and not the mean", "why do you look at the worst days", "why a tail metric",
             "does the result change at other tail levels"],
         say="CVaR 95 is the average over the worst 5% of days, which is where the risk lives for a carbon "
             "commitment; a mean hides the bad days. It is also the risk measure the robust layer is meant to "
             "protect. The robust gap stays null at the 0.90 and 0.99 tail levels too.",
         src="README.md (Glossary; What moves the results); " + SNAP + "dro_tail_sensitivity_2026-06-25.csv"),
    dict(key="falsification", title="the pre-committed falsification test", view="evidence",
         kw={"falsif": 3, "shuffl": 3, "marginal": 1.5, "pre": 1, "commit": 2, "registr": 2, "preregist": 3,
             "experiment": 1.5, "design": 1, "test": 0.5, "lock": 2},
         ex=["what is the shuffled marginals test", "how did you test whether correlation helps",
             "what does pre committed mean", "how was the experiment designed", "was it pre registered"],
         say="The scheduler is fitted twice: once on the real joint covariance, once on a block-diagonal one where "
             "all cross-region links are destroyed but each region keeps its own pattern. The difference in "
             "out-of-sample CVaR is the value of spatial correlation. The protocol was commit-locked, dry-run on "
             "training data, then read once on 2025.",
         src="README.md (Method; Glossary)"),
    dict(key="solver", title="solvers and run time", view=None,
         kw={"solver": 3, "solve": 2, "fast": 1.5, "runtime": 2, "time": 0.5, "long": 0.5, "second": 1, "gurobi": 3,
             "clarabel": 3, "highs": 3, "tractab": 3, "scal": 1.5, "compute": 0.5, "socp": 2, "cone": 2},
         ex=["which solver do you use", "how long does a solve take", "is it tractable", "does it scale",
             "do you need gurobi"],
         say="It uses free solvers only: Clarabel for the cone program and HiGHS for the linear programs. One cone "
             "program solves in 0.19 to 0.26 seconds and a 1,000-scenario CVaR program in 0.9 to 1.3 seconds on a "
             "laptop. The whole study, about ten thousand solves, runs in under two hours on one core.",
         src="thesis/capstone_thesis.tex (Computational considerations)"),
    # ---------------------------------------------------------- data
    dict(key="data", title="the data", view=None,
         kw={"data": 2, "dataset": 3, "source": 1.5, "electricity": 2, "maps": 1.5, "hourly": 1.5, "year": 1,
             "train": 1.5, "test": 0.5, "split": 2, "observation": 2, "licen": 1.5, "period": 1},
         ex=["what data did you use", "where does the carbon data come from", "what is the train test split",
             "how many years of data", "is the data licensed"],
         say="Hourly carbon intensity from Electricity Maps under an academic licence, 2021 to 2025, 43,824 hours "
             "per zone. Models train on 2021 to 2024 and are tested once on 2025, and walk-forward checks repeat "
             "that for 2022, 2023 and 2024. The raw data is never shipped; only derived summaries are committed.",
         src="thesis/capstone_thesis.tex (Data); docs/results_snapshots/README.md"),
    dict(key="grids", title="the three grids and regions", view="command",
         kw={"grid": 2, "region": 1.5, "zone": 2, "which": 0.5, "portfolio": 2, "western": 1.5, "eastern": 1.5,
             "diversified": 2, "iberia": 1, "europe": 1, "geograph": 2, "where": 0.3},
         need=r"\bgrids?\b|region|zone|portfolio|western|eastern|diversified|geograph|where.*(test|run|stud)",
         ex=["which regions did you study", "what are the three grids", "which zones are in each portfolio",
             "why these regions"],
         say="Three grids that span the dependence spectrum. Western US: California ISO, Sacramento, Los Angeles, "
             "Nevada and Arizona, strongly correlated. Eastern US and Canada: Ontario, New York, the Midwest and "
             "Mid-Atlantic. And a Diversified mix of California solar, Texas wind and Bonneville hydro, built to be "
             "nearly uncorrelated, the best case for spatial modelling.",
         src="README.md (The three grids)"),
    dict(key="europe", title="Europe and other grids", view=None,
         kw={"iberia": 3, "spain": 3, "portugal": 3, "france": 3, "europe": 3, "european": 3, "california": 1,
             "nevada": 1, "other": 0.5, "generali": 2, "more": 0.3},
         ex=["did you test it in europe", "what about spain and france", "does it generalise to other grids",
             "did you try more regions"],
         say="The same machinery was run on a California and Nevada set and on an Iberia and France panel, and both "
             "showed the same null. Iberia is reported as corroboration only, a weaker test. Grids with very "
             "different mixes, like hydro-thermal systems with seasonal storage, remain untested.",
         src="README.md (The three grids); thesis/capstone_thesis.tex (Limitations iv)"),
    dict(key="baselines", title="the baselines", view="evidence",
         kw={"baseline": 3, "carbon": 0.3, "blind": 2, "agnostic": 2, "greedy": 2.5, "threshold": 2, "naive": 2,
             "simple": 1, "heuristic": 2, "against": 1},
         ex=["what baselines did you compare against", "how does it do against a greedy scheduler",
             "what is the no transfer baseline", "compared with a carbon blind scheduler"],
         say="Against a carbon-blind schedule, the transfer optimiser cuts worst-day emissions by 6.0% in the West, "
             "10.4% in the East and 12.3% on the Diversified grid. A greedy time-shifter gets 2.0%, 0.5% and 3.6%. "
             "Inside the thesis each question has its own like-for-like baseline: no transfer for RQ1, shuffled "
             "covariance for RQ2, and the deterministic plan for RQ3.",
         src=SNAP + "external_baselines_2026-07-12.csv"),
    dict(key="carbon_accounting", title="carbon accounting", view=None,
         kw={"carbon": 1, "accounting": 3, "account": 2, "intensity": 2, "lifecycle": 3, "marginal": 2, "scope": 2,
             "measur": 1.5, "calculat": 1.5, "pue": 2, "gram": 1.5, "tonne": 1.5},
         need=r"account|intensity|lifecycle|marginal|scope|measur|calculat|count|pue|gram|tonne|how much carbon",
         ex=["how do you account for carbon", "how are emissions calculated", "is it marginal or average intensity",
             "what carbon intensity do you use", "how do you measure emissions"],
         say="Emissions are carbon intensity times energy, summed over every region and hour, using Electricity Maps' "
             "hourly lifecycle intensity in grams per kilowatt hour. It is the grid-average number, not a marginal "
             "signal, and that is a stated limitation. In the revised feasible set a PUE term ties wall power to "
             "IT power, so hot hours cost more.",
         src="thesis/capstone_thesis.tex (Data; Limitations v); thesis/full_formulation.md (3b)"),
    # ---------------------------------------------------------- results
    dict(key="rq1", title="RQ1: does moving work pay", view="evidence",
         kw={"migration": 2.5, "rq1": 3, "lever": 2, "headline": 2.5, "move": 1, "between": 0.5, "region": 0.5, "pay": 1,
             "save": 1.5, "saving": 1.5, "much": 0.5, "first": 0.5},
         ex=["does moving work between regions pay", "how much does migration save", "what is the rq1 result",
             "what is the lever that pays", "how much do you save by moving jobs"],
         say="Yes. Letting work move between regions cuts out-of-sample CVaR 95 by 4.0% on the Western grid, 9.9% "
             "on the Eastern and 9.0% on the Diversified, compared with no transfer. The saving comes from shipping "
             "work to whichever region is cleanest on average, not from any dependence model.",
         src=SNAP + "part3_transfer_value_2026-06-15.csv"),
    dict(key="transfer_budget", title="how much work needs to move", view="evidence",
         kw={"budget": 3, "phi": 3, "plateau": 3, "how": 0.3, "much": 0.5, "move": 0.5, "need": 0.5, "share": 1.5,
             "curve": 2, "percent": 0.5},
         ex=["how much work needs to move", "what is the transfer budget", "where does the saving plateau",
             "what happens if you move less"],
         say="Not much. The saving levels off once about 20% of the work may move. Even a 10% budget gets 7.8% in "
             "the East and 7.1% on the Diversified grid, and the West is already at its plateau.",
         src=SNAP + "transfer_value_curve_2026-06-24.csv"),
    dict(key="rq2", title="RQ2: does modelling correlation help", view="evidence",
         kw={"correlation": 2.5, "rq2": 3, "spatial": 1.5, "matter": 1, "add": 0.5, "second": 0.3,
             "joint": 1},
         ex=["does modelling correlation help", "does spatial correlation matter", "what is the rq2 result",
             "does the covariance add anything"],
         say="No. Across 144 pre-committed cells the gap between the joint and the shuffled covariance stays under "
             "the 0.4% materiality margin; the largest was 0.35% of CVaR. Equivalence tests rule out any effect "
             "above that margin, so this is a positive claim of no material value, not a failure to find one.",
         src=SNAP + "bh_correction.csv; docs/results_snapshots/README.md"),
    dict(key="mean_dominance", title="why correlation adds nothing: mean dominance", view="evidence",
         kw={"mean": 1.5, "dominance": 3, "domin": 3, "why": 0.5, "mechanism": 3, "ablation": 3, "flatten": 2,
             "tail": 1, "chi": 2, "asymmetr": 2, "explain": 0.3},
         need=r"(why|how come|reason|explain).*(correlat|covarian|dependen|co.?mov|spatial|copula)|mechanism|"
              r"dominan|ablation|flatten|tail", boost=3,
         ex=["why doesn't correlation help", "what is mean dominance", "what is the mechanism behind the null",
             "how come the covariance does not matter"],
         say="Because the swing in average carbon between regions is much larger than how they co-move, so the mean "
             "pins the schedule. The covariance signal is real: flatten the means and it is worth up to 1.46%. And "
             "what dependence is left sits in the clean tail, regions clean together but dirty apart, which a "
             "covariance ball cannot see.",
         src="README.md (The finding, RQ2); " + SNAP + "tail_dependence_2026-07-05.csv"),
    dict(key="copulas", title="copulas", view="evidence",
         kw={"copula": 3, "clayton": 3, "gaussian": 2, "comonoton": 3, "vine": 2, "nonlinear": 1.5,
             "non": 0.3, "elliptical": 2},
         ex=["did you try copulas", "what about a clayton copula", "does a non elliptical model help",
             "what is the comonotone ceiling"],
         say="Yes, as a check on RQ2. Gaussian, lower-tail Clayton and even the comonotone copula, perfect lockstep, "
             "were run as CVaR schedulers over the same feasible set. Even the most extreme coupling recovers "
             "nothing material, about 0.1% of CVaR or less.",
         src="thesis/capstone_thesis.tex (Appendix copula); " + SNAP + "*_copula_2026-06-13.csv"),
    dict(key="rq3", title="RQ3: does robust optimisation pay", view="evidence",
         kw={"rq3": 3, "robust": 2.5, "robustness": 2.5, "dro": 1.5, "hedg": 2, "pay": 1.5, "crossover": 3,
             "worth": 1, "price": 1.5},
         ex=["does robust optimisation pay", "when does dro pay off", "what is the rq3 result",
             "is robustness worth it", "what is the price of robustness"],
         say="Only in emergencies real grids do not reach. The robust layer starts to pay at a severity of about 3 "
             "times, a tripling of carbon in a rare event, while the observed joint-grid severities are 1.29 to "
             "1.89 times. Under multi-seed testing that crossover survives only on the Western grid, and only "
             "marginally, so it is reported as a decision rule, not a universal threshold.",
         src=SNAP + "part3_emergency_2026-06-15.csv; " + SNAP + "carbon_ceiling_2026-06-24.csv"),
    dict(key="severity", title="severity M and real emergencies", view="evidence",
         kw={"sever": 3, "emergenc": 3, "spike": 2, "storm": 2, "uri": 2, "extreme": 1.5, "event": 1,
             "observed": 1, "real": 0.5},
         ex=["what is the severity m", "how bad do real emergencies get", "what about winter storm uri",
             "how extreme are real carbon spikes"],
         say="M is how many times carbon intensity spikes in a rare grid emergency, so 3 is a tripling. Across 17 "
             "zones the per-zone median is about 1.43, and on the comparable joint-grid axis it is 1.29 to 1.89. "
             "Some very low-carbon zones spike harder in relative terms, which is why the comparison uses the same "
             "joint portfolio axis as the scheduler.",
         src=SNAP + "carbon_ceiling_2026-06-24.csv; README.md (Headline numbers)"),
    dict(key="online", title="forecast error and the online test", view="evidence",
         kw={"online": 3, "rolling": 3, "horizon": 2, "forecast": 1.5, "error": 1, "day": 0.3, "ahead": 1,
             "part": 0.5, "realtime": 2, "live": 0.5, "vss": 3, "diversified": 1, "worse": 2, "hurt": 2},
         need=r"online|rolling|horizon|forecast|day ahead|real time|realtime|part 4|stochastic solution|vss|worse|"
              r"hurt",
         ex=["what happens with forecast error online", "how does it do in a rolling horizon",
             "what is the day ahead forecast", "does robustness help when forecasts are wrong"],
         say="Day-ahead, the forecast is a transparent hour-of-day mean. Run online on about 120 test days, the "
             "robust plan's CVaR gap is +0.28% in the West and +0.04% in the East, both with intervals spanning "
             "zero. On the Diversified grid it is 10.3% worse, so hedging there actually hurts.",
         src=SNAP + "part4_online_2026-06-15.csv; thesis/capstone_thesis.tex (Limitations vi)"),
    dict(key="null_result", title="the null result and why it still matters", view="evidence",
         kw={"null": 3, "failure": 2, "fail": 2, "negative": 2, "nothing": 1.5, "valuable": 2, "value": 0.5,
             "worth": 0.5, "substantive": 3, "matter": 1, "disappoint": 2, "useful": 1.5, "honest": 1.5},
         ex=["isn't a null result a failure", "why is the null still substantive", "why does a negative result matter",
             "what is the null result", "so you found nothing", "is the null result useful"],
         say="It is a measured null, not a missing result. The test was pre-committed, the robust layer genuinely "
             "engaged, the schedule still had room to move, and a positive control showed the instrument can detect "
             "a 1.46% effect, yet every gap stayed inside the 0.4% margin. For an operator that is a saving: it says "
             "skip the expensive dependence model and fund the transfer channel instead.",
         src="README.md (The finding); thesis/full_formulation.md; " + SNAP + "bh_correction.csv"),
    dict(key="robustness_checks", title="robustness checks", view="evidence",
         kw={"robustness": 1, "check": 2, "sensitiv": 2.5, "trust": 1, "sure": 1, "ledoit": 3, "wolf": 2,
             "bootstrap": 2.5, "walk": 2, "forward": 1.5, "battery": 3, "stress": 2, "verify": 1.5, "valid": 1},
         need=r"check|sensitiv|sure|ledoit|bootstrap|walk|battery|stress|verif|valid|robust to|confiden|"
              r"how robust|robust is|hold up", boost=3.5,
         ex=["how do you know the result is robust", "what robustness checks did you run",
             "did you do sensitivity analysis", "how sure are you of the result"],
         say="A full battery: Ledoit-Wolf shrinkage, seasonal and AR(1) residuals, Benjamini-Hochberg over 144 cells, "
             "block bootstrap, tighter ramps and 50 to 95% utilisation. Walk-forward to 2022, 2023 and 2024 "
             "reproduces the null, the largest gap 0.21%. Utilisation moves the CVaR level a lot but the gap by at "
             "most 0.28 points.",
         src="README.md (Method; What moves the results); docs/results_snapshots/README.md"),
    dict(key="significance", title="statistics and significance", view="evidence",
         kw={"significan": 3, "statistic": 2.5, "tost": 3, "equivalence": 3, "p": 1, "value": 0.5, "power": 2,
             "confidence": 2, "interval": 2, "hochberg": 2, "benjamini": 2, "multiple": 1.5, "margin": 2},
         ex=["is it statistically significant", "what is the tost test", "how do you handle multiple testing",
             "what is the materiality margin", "did you have enough statistical power"],
         say="Each cell gets a TOST equivalence test against a 0.4% materiality margin, so the claim is that any "
             "effect above 0.4% is ruled out. Benjamini-Hochberg at q 0.05 controls for testing 144 cells, and a "
             "power analysis checks the test could have seen a material effect. Intervals come from a 1,000-resample "
             "paired bootstrap.",
         src="README.md (Method); thesis/capstone_thesis.tex"),
    dict(key="one_day_vs_thesis", title="one-day numbers versus thesis numbers", view="command",
         kw={"14": 2, "37": 2, "one": 0.5, "day": 1, "illustration": 3, "differ": 1.5, "why": 0.3, "bigger": 2,
             "higher": 1.5, "console": 1, "demo": 0.5, "inconsistent": 2},
         need=r"14|37|illustration|one day|one-day|bigger|higher|differ|console|screen|demo number",
         ex=["why does the demo show 14% but the thesis says 4%", "why is the one day saving bigger",
             "are the console numbers the same as the thesis", "why do the numbers differ"],
         say="The console plans one day with one budget and scores the average, so it is an illustration. On 15 "
             "June 2025 moving up to 30% of the work saves 14.4% in the West versus time shifting alone. The thesis "
             "number, 4.0 to 9.9%, is out of sample over a whole year and measures the worst 5% of days, so the two "
             "are not comparable.",
         src="README.md (After the capstone, example)"),
    dict(key="recommendation", title="the business takeaway", view="evidence",
         kw={"recommend": 3, "takeaway": 3, "business": 2.5, "company": 1.5, "operator": 2, "should": 1,
             "invest": 2, "practical": 2, "implication": 2, "lesson": 2, "decision": 1, "manager": 2, "value": 0.5},
         ex=["what should a company do with this", "what is the business takeaway", "what would you recommend",
             "what is the practical lesson", "what does this mean for an operator"],
         say="Invest in the simple lever first: a per-region scheduler plus the ability to move work between "
             "regions. Skip the richer dependence models, and treat robust optimisation as a conditional option "
             "you switch on only if forecast surprises grow. Gridshift's drift monitor is the trigger for that "
             "re-check.",
         src="agentic/findings.py; README.md (The finding)"),
    dict(key="limitations", title="limitations", view=None,
         kw={"limitation": 3, "weak": 2, "wrong": 1.5, "critic": 2.5, "critique": 2, "missing": 1.5, "referee": 2,
             "reviewer": 2,
             "assumption": 2, "assum": 1.5, "risk": 0.3, "threat": 2, "validity": 1.5},
         ex=["what are the limitations", "what are the weaknesses of the study", "what would a critic say",
             "what assumptions did you make", "what could be wrong"],
         say="Four matter most. The migration saving is gross: no network, latency or SLA cost, so it is an upper "
             "bound. The workload is a stylised one, not real operator traces. It uses grid-average lifecycle "
             "carbon, and the primary test is one held-out year, backed by walk-forward checks.",
         src="thesis/capstone_thesis.tex (Limitations)"),
    dict(key="migration_cost", title="migration cost, latency and data rules", view=None,
         kw={"cost": 2, "latency": 3, "bandwidth": 3, "network": 2, "sla": 3, "expensive": 2, "price": 0.5,
             "sovereign": 3, "gdpr": 3, "residency": 3, "privacy": 2, "money": 2, "dollar": 2, "economic": 2},
         ex=["isn't moving work expensive", "what about latency and bandwidth", "what about data sovereignty",
             "did you include migration cost", "what about the money side"],
         say="The headline saving ignores migration cost, so treat it as an upper bound. For splittable batch jobs "
             "bandwidth and latency are modest next to the carbon avoided, so the 4.0% plateau should survive, but "
             "that is not quantified. Where data may be processed is a governance question, which is why every move "
             "needs a person's approval.",
         src="thesis/capstone_thesis.tex (Limitations i); README.md (After the capstone)"),
    dict(key="future", title="what I would do next", view=None,
         kw={"future": 3, "next": 1.5, "improve": 2, "differently": 2, "again": 1, "roadmap": 2, "paper": 1.5,
             "publish": 1.5, "more": 0.3},
         ex=["what would you do next", "what is the future work", "what would you improve with more time",
             "what would you do differently", "how would you extend this"],
         say="First, add migration economics and a marginal emissions signal, so the saving is a net figure. "
             "Second, a copula-ambiguity Wasserstein DRO that robustifies the dependence itself, and an online, "
             "multistage version with limited recourse. Third, turn the mean-dominance bound into a general test "
             "for when cross-region dependence can ever matter.",
         src="thesis/capstone_thesis.tex (Future work; Limitations)"),
    dict(key="reproducibility", title="reproducibility and trust", view=None,
         kw={"reproduc": 3, "trust": 2, "replicat": 2, "integrity": 3, "sha": 3, "snapshot": 2.5, "ci": 1.5,
             "test": 1.5, "pipeline": 0.5, "audit": 1.5, "rigor": 2, "rigour": 2},
         ex=["can I reproduce the results", "why should I trust the numbers", "how is the work kept honest",
             "how many tests are there"],
         say="Every reported number traces to a small summary CSV frozen by a SHA-256 manifest that CI checks on "
             "every push. Experiments were commit-locked before the test year was read, seeds are fixed, and the "
             "README states 213 tests collected, 200 of them in public CI.",
         src="README.md (header; Status; Integrity policy)"),
    # ---------------------------------------------------------- agent layer
    dict(key="agentic", title="the agent layer", view=None,
         kw={"agent": 2.5, "agentic": 3, "workflow": 2.5, "layer": 0.5, "autonomous": 2, "step": 1, "pipeline": 1,
             "architecture": 2, "gridshift": 1.5, "llm": 1},
         ex=["what is the agentic layer", "why a workflow and not an agent", "how does gridshift work",
             "what are the five steps", "is this autonomous"],
         say="It is a fixed five-step workflow, all code: check the rules, forecast, optimise, explain, then wait "
             "for a person's approval. The decision is an optimisation with guarantees, so letting a language model "
             "choose the steps would add cost and risk and buy nothing. Nothing is ever executed on its own.",
         src="README.md (After the capstone)"),
    dict(key="ontology", title="the ontology and reasoner", view="knowledge",
         kw={"ontology": 3, "rule": 1.5, "infer": 2.5, "inference": 2.5, "triple": 3, "semantic": 2, "graph": 1.5,
             "allowed": 1, "know": 0.5},
         ex=["what does the ontology do", "how does it know which job may move", "what is the knowledge graph",
             "how many triples does the reasoner infer", "what is the semantic layer"],
         say="The rules about what may move live in an OWL ontology, not in code branches. A reasoner grows "
             "{asserted} asserted facts into {reasoned}: training is a flexible job so it may move, the checkout "
             "service is fixed, and a property chain works out which regions each job can reach. Every metric is "
             "also defined once there, so people and agents read saving the same way.",
         src="agentic/ontology.ttl; live counts from agentic/knowledge.py"),
    dict(key="monitoring", title="how the monitoring works", view="monitor",
         kw={"monitor": 3, "drift": 2, "mlop": 3, "weekly": 2, "github": 1.5, "action": 0.5, "alarm": 1,
             "retrain": 2, "watch": 1.5, "observ": 1},
         need=r"how|what|explain|work|set up|mlops|why|weekly|retrain",
         ex=["how does the monitoring work", "how do you watch for drift", "what is the mlops part",
             "what happens when the forecast drifts", "does it retrain"],
         say="The forecast refits every day by construction, so the risk is drift. Each month the monitor compares "
             "forecast error with the first {base} months and raises an alert at {thr} times. An alert names the "
             "decision to revisit, whether robust optimisation now pays, and a weekly GitHub Actions job re-runs the "
             "check. Ask is the forecast drifting for the live numbers.",
         src="agentic/monitoring.py; .github/workflows/agentic-weekly.yml"),
    dict(key="tools", title="tools: MCP and A2A", view="interfaces",
         kw={"mcp": 3, "a2a": 3, "tool": 2.5, "interface": 2, "api": 1.5, "protocol": 2, "integrat": 2,
             "copilot": 2, "other": 0.3, "plug": 2},
         ex=["what tools does it expose", "how do other agents use it", "what is the mcp server",
             "what is a2a used for", "how would this integrate with copilot"],
         say="Two ways in. Over MCP an agent gets {ntools} tools, {ro} read only and the rest draft only, plus the "
             "ontology and findings as resources. Over A2A another company's agent hands over a whole task in plain "
             "language; the agent card lists {nskills} skills.",
         src="agentic/mcp_server.py; agentic/a2a.py"),
    dict(key="evals", title="how the agent is tested", view="interfaces",
         kw={"eval": 3, "evaluat": 2.5, "accura": 2.5, "label": 2, "routing": 2, "route": 1.5, "test": 1,
             "quality": 1.5, "correct": 1},
         need=r"eval|accura|label|rout|test the (agent|router|assistant)|quality|correct", boost=2,
         ex=["how do you evaluate the agent", "what are the evals", "how accurate is the routing",
             "how do you test the router"],
         say="A labelled eval of {ncases} plain-language requests, each with the expected tool and outcome. Routing "
             "and end-to-end are both 100%: a fixed job is never proposed for migration, and an unclear request is "
             "asked back. It runs on every change and in the weekly job.",
         src="agentic/evals.py; README.md (Evals)"),
    dict(key="human_loop", title="safety and human approval", view="command",
         kw={"approval": 3, "human": 2, "safe": 2, "safety": 2, "execut": 2, "automat": 1.5, "control": 1,
             "audit": 2, "govern": 2, "oversight": 3, "trust": 0.5, "itself": 2, "own": 1},
         need=r"by itself|on its own|human|approv|sign|safe|execut|audit|oversight|automatic|autonomous|govern",
         boost=3,
         ex=["is there a human in the loop", "can it move work on its own", "how is it kept safe",
             "who approves the moves", "is there an audit log"],
         say="Every proposal ends as pending approval and nothing is ever executed. Moving work changes where data "
             "is processed, so the operations lead signs it off, and approve or reject is written to an audit log. "
             "The ontology also blocks user-facing jobs from moving at all.",
         src="agentic/workflow.py; agentic/console.py (decide)"),
    dict(key="voice_tech", title="how this voice works", view=None,
         kw={"voice": 2.5, "llm": 2, "understand": 1.5, "nlp": 2, "neural": 2, "edge": 1.5, "offline": 1.5,
             "hear": 1, "answer": 0.5, "assistant": 1},
         ex=["how does the voice work", "are you using an llm", "is this chat gpt", "how do you understand me",
             "do you need the internet"],
         say="No language model. Questions are matched offline by a small scorer over keywords and example "
             "phrasings, and plans come from the optimiser. The voice is a neural edge-tts voice with cached audio, "
             "the browser voice is the fallback, and captions always show.",
         src="agentic/faq.py; agentic/voice.py"),
    dict(key="forecast", title="the forecast model", view=None,
         kw={"forecast": 3, "machine": 1.5, "learn": 2, "neural": 2, "predict": 2, "ml": 2, "model": 0.5,
             "simple": 1, "climatolog": 3},
         need=r"machine learning|\bml\b|neural|learn|predict|forecast(er|ing)? (model|method)|what forecast|"
              r"which forecast|how .*forecast|why not .*forecast|climatolog",
         boost=2,
         ex=["what forecast model do you use", "did you use machine learning for the forecast",
             "why not a neural network forecaster", "how is carbon predicted"],
         say="Deliberately simple: the hour-of-day mean, updated daily, and the console uses the previous 14 days. "
             "That keeps the robustness result about hedging error, not about one forecaster. A learned model would "
             "only shrink the error the DRO hedges, so the robustness premium would shrink further.",
         src="thesis/capstone_thesis.tex (Limitations vi); agentic/scheduler.py"),
    dict(key="production", title="how it would run in production", view=None,
         kw={"production": 3, "deploy": 3, "real": 0.5, "world": 1, "scale": 1, "operat": 1, "integrat": 1.5,
             "enterprise": 2, "company": 0.5, "rollout": 2, "pilot": 2},
         ex=["how would you deploy this in production", "how would a company use this for real",
             "what would a real rollout look like", "how would you pilot this"],
         say="As the same five-step workflow behind MCP or A2A, so an operator's own agents can call it. Each day it "
             "proposes a plan from the forecast, a person approves it, and the drift monitor and weekly job say when "
             "to revisit the robust layer. A pilot would start with one flexible batch workload and a small transfer "
             "budget, since about 20% already reaches the plateau.",
         src="README.md (After the capstone); " + SNAP + "transfer_value_curve_2026-06-24.csv"),
    dict(key="run_demo", title="how to run the demo", view=None,
         kw={"run": 2.5, "demo": 1.5, "local": 1.5, "localhost": 2, "server": 2, "command": 1, "start": 1,
             "open": 0.5, "use": 0.3, "cache": 1.5, "warm": 2, "laptop": 1, "console": 0.5},
         need=r"run|start|launch|install|set ?up|spin|serve|open|warm|use (the|this) (demo|console)|how do i", boost=1.5,
         ex=["how do I run the demo", "how do I start gridshift", "how do I launch the console",
             "what do I need to run it", "how do I set it up"],
         say="Run python -m agentic.serve and it opens localhost:8765. The night before, run agentic.warm_cache "
             "once so plans and audio are ready offline. In the app, hold space or tap the mic to ask, "
             "and say present for the three-minute tour.",
         more="Commands: .venv\\Scripts\\python -m agentic.serve ; .venv\\Scripts\\python -m agentic.warm_cache "
              "(then --check). GRIDSHIFT_TTS=off turns the neural voice off; GRIDSHIFT_NO_DATA=1 simulates a "
              "machine without the licensed data.",
         src="README.md (Gridshift console (local))"),
]

HELP_GROUPS = [
    ("The project", ["What is the capstone about?", "What are the research questions?", "What is new here?"]),
    ("Method", ["How does the model work?", "What is the ambiguity set?", "Why was the feasible set revised?",
                "Why DRO and not stochastic programming?", "How do you choose epsilon?"]),
    ("Data and baselines", ["What data did you use?", "Which regions did you study?",
                            "What baselines did you compare against?", "How do you account for carbon?"]),
    ("Results", ["Does moving work pay?", "Does modelling correlation help?", "Does robust optimisation pay?",
                 "Why is the null still substantive?", "What robustness checks did you run?"]),
    ("Critique", ["What are the limitations?", "What would you do next?", "Isn't moving work expensive?"]),
    ("Agent layer", ["Why a workflow and not an agent?", "How does the monitoring work?", "What tools does it expose?",
                     "How do you evaluate the agent?"]),
    ("Demo", ["How do I run the demo?", "Plan the model training for June 15th", "Present"]),
]

HELP_SAY = ("You can ask about the method, the ambiguity set and the constraints, the data and baselines, the three "
            "results and why the null still matters, limitations and next steps, why DRO, carbon accounting, the "
            "agent layer, and how to run the demo. Or ask me to plan a job, for example the model training for "
            "June 15th.")

_HELP = re.compile(r"\b(what can (i|you) (ask|say|do)|what (should|could|else can) i ask|what do you know|"
                   r"what (questions|topics)|which topics|menu)\b|^\s*(please\s+)?help\b|\bhelp me\b|"
                   r"\bi need help\b")

BY_KEY = {t["key"]: t for t in TOPICS}
_EX_TOKENS = {t["key"]: [tokens(e) for e in t["ex"]] for t in TOPICS}
THRESHOLD = 2.0


def _has(q: set[str], key: str) -> bool:
    return key in q or (len(key) >= 5 and any(w.startswith(key) for w in q))


def scores(text: str) -> list[tuple[float, str]]:
    """(score, key) for every eligible topic, best first."""
    low = text.lower()
    q = tokens(text)
    if not q:
        return []
    out = []
    for t in TOPICS:
        if t.get("need") and not re.search(t["need"], low):
            continue
        kw = sum(w for k, w in t["kw"].items() if _has(q, k)) + (t.get("boost", 0) if t.get("need") else 0)
        # how much of the closest example question this one covers
        ex = max((len(q & e) / max(3, len(e)) for e in _EX_TOKENS[t["key"]]), default=0.0)
        out.append((round(kw + 3.0 * ex, 3), t["key"]))
    return sorted(out, reverse=True)


def is_help(text: str) -> bool:
    return bool(_HELP.search(text.lower()))


def match(text: str) -> str | None:
    """The topic key this question is about, or None when nothing is confident enough."""
    s = scores(text)
    if not s or s[0][0] < THRESHOLD:
        return None
    return s[0][1]
