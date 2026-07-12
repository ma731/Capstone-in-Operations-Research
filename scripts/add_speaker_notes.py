"""Add speaker notes (Presenter View talk track) to the defense deck.

Notes appear only in PowerPoint Presenter View, not on the shared/projected
slide, so on Zoom the judges see the slide while the presenter reads the notes.

Run:  .venv/Scripts/python -m scripts.add_speaker_notes
Reads the freshly built deck (deck/capstone_defense_v2.pptx) and writes notes
into it plus the two Desktop copies (v2 and Marco). Safe: only sets notes text,
never touches slide shapes/layout. Re-run any time after a rebuild.
"""
from __future__ import annotations

import os
from pathlib import Path
from pptx import Presentation

ROOT = Path(__file__).resolve().parents[1]
DECK = ROOT / "deck" / "capstone_defense_v2.pptx"
DESKTOP = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "OneDrive" / "Escritorio"

# Per-slide talk track. Keep scannable: timing, the beats, exact numbers, cues.
NOTES = {
1: """[0:35] TITLE
Good morning, thank you for being here.
One plain question: in carbon-aware data-center scheduling, when is a fancier model actually worth it? A fancier model always feels safer; this asks whether it earns the bill.
The field already moves work to cleaner hours and places, and it works. But every paper stacks another layer and assumes it pays. Nobody measured it.
We built one real scheduler and priced three upgrades, one at a time. Result: ONE pays, TWO do not.""",

2: """[0:50] THE CASE IN ONE SLIDE
Meet the operator: flexible compute across regions, three decisions each evening. Stand-in for the real study: 3 grids, 17 zones.
D1 move work between regions? YES. Worst-day emissions fall 4 to 10%, ~$1.7M/yr on one fleet (gross, no statistics). The lever.
D2 model how regions move together? NO. Under 0.4%, below the noise, ~$37k, not reliably positive.
D3 buy insurance for bad days? Only if carbon can TRIPLE. Real grids peak ~1.4x.
Underneath: a rule for when a dependence model can pay, and a fair way to price any layer.
Hold onto: ONE LEVER, TWO SKIPS.""",

3: """[0:40] MEET THE OPERATOR
You run data centers across US and Canada with a carbon promise. Every evening you pick where tomorrow's flexible work runs.
Two facts: the WORK CAN WAIT (a training/batch job can start later or run cleaner, nobody notices). The GRID WILL NOT WAIT (cleanliness swings by hour and place). Same hour looks completely different across regions on this map.
Google and Microsoft already do this at production scale.
So the question is not WHETHER to shift work. It is HOW FANCY the model needs to be.""",

4: """[0:45] THE GAP
Why still open? Three reasons.
1. Savings never separated: papers change many things at once, report one big number.
2. No fair baseline: richer models compared under different rules, so model and setup get tangled.
3. Closest work (Hall et al 2024) does robust scheduling for a SINGLE region. Whether the links ACROSS regions pay was open.
Our fix is discipline, not a new algorithm: one scheduler, same rules every version, add one layer at a time, price each on data it never saw.""",

5: """[1:05] THE MACHINE AND THE RULES  (constraints live here)
Machine: every evening forecast carbon per region, plan where/when work runs, execute, score. Repeat over a full held-out year (2025).
RULES OF THE GAME (slow down): capacity ceiling; power RAMPS not jumps (15 MW/h); a DEADLINE stops dumping all work in the single cheapest hour; a THERMAL limit (hot hours cost cooling, less compute) = where weather enters.
Two fairness rules: every version runs under IDENTICAL constraints (only the brain changes); baseline is like-for-like, same scheduler with transfer OFF (Phi=0).
In our favor: constraints calibrated to bind LOOSELY, schedule still moves 25-30%, so fancier models get their best shot.
Ruler: CVaR = average of the worst 5% of days. Matches exact optimum on small problems. Full model on last backup.""",

6: """[0:45] THE DATA
Real hourly carbon (Electricity Maps) 2021-2025, 17 zones US/Canada. Trained to 2024, tested ONCE on 2025.
Three grids chosen to work AGAINST our conclusion: US West (regions move together strongly, up to 0.78); Eastern belt (middle); built portfolio of solar/wind/hydro (barely linked, the BEST case for co-movement). If it can pay anywhere, it pays there.
Iberia/France checked early, set aside: robust machinery doesn't engage, a zero there proves nothing. We keep only tests that could have failed.""",

7: """[0:55] DECISION 1 - MOVE THE WORK?  YES.
Ran the test year twice, transfer on vs off, measured the gap. Worst-day emissions fall: Western 4.0%, Eastern 9.9%, Diversified 9.0%. Eastern fleet ~ $1.7M/yr.
(PAUSE)
Two points: savings FLATTEN near a 20% transfer budget (a modest channel gets nearly all the value). And it needs NO statistics, just a forecast and a channel.
Scope: the dollar figure is a GROSS ceiling, before the cost of moving work. But this is the lever. Everything else is measured against it.""",

8: """[0:35] ONE JUMP, THEN FLAT
This one picture is the whole thesis. Value up, complexity right. Same rules, same test year.
Exactly ONE jump, and it is transfer. After that flat: co-movement, robustness, copulas, almost no extra height.
Rest of the talk answers two questions about this picture: why is the line flat, and when would it not be?""",

9: """[0:55] DECISION 2 - MODEL THE LINKS?  NO.
Regions really do move together (you saw 0.78). Question is not whether links exist, but whether KNOWING them helps the scheduler.
Test fixed in advance in version control BEFORE reading the test year: fit the schedule with real links, then with links destroyed (each region keeps its own daily pattern). If links matter, real-links must win.
It does not. Across 144 pre-committed cells (4 grids x 9 regimes x 4 estimators), gap never leaves +/- 0.4%. Biggest 0.355%, sign flips.
ACTIVE zero: machinery on and engaged, had every chance, found nothing. Skip this layer. Why? Best part next.""",

10: """[1:20] THE TWIST - WAVE AND RIPPLE  (positive control)
[JUDGES: both Pablo and Nacho will hammer the null's credibility. Lead with +1.46%.]
Carbon follows a BIG DAILY WAVE (sun + demand): large, shared, easy to predict. The links live in a SMALL RIPPLE on top. Schedule follows the wave; ripple too small to change its mind. On every grid, wave is 2 to 4x the ripple.
But how do I know my test isn't just too weak?
(STOP. Pause before and after the number.)
We flattened the wave artificially and re-ran the IDENTICAL test. The same layer suddenly pays +1.46%. Far above the 0.4% bar.
(PAUSE)
So the instrument fires. That is why the zero is trustworthy. Signal is real, just too small and shaky to bank; it loses to the wave.
Travels beyond this dataset: a dependence layer only pays when the RIPPLE RIVALS THE WAVE. Anyone can check their own grid in an afternoon.""",

11: """[0:55] DECISION 3 - BUY INSURANCE?  (the DRO math)
[JUDGES: Nacho uses optimal transport himself - can go deep on the Wasserstein ball. Be ready.]
Forecasts miss. Robust plan does not trust one forecast: draws a BALL of plausible tomorrows and plans against the worst inside. Like packing for weather a bit worse than predicted.
Read the equation: minimize TWO terms. First (forecast carbon x schedule) = the carbon bill, carries the saving. Second = caution surcharge: epsilon (one dial for how much you distrust the forecast) x how exposed the plan is to shared swings.
Epsilon = 0 -> plain forecast-only plan. Turn it up -> hedges. Convex, free solver in seconds.
Real question: how bad must the bad day get before that surcharge pays for itself?""",

12: """[0:55] THE CROSSOVER
Injected emergencies into the test year, turned severity up step by step. Robust plan starts to win once carbon spikes to ~3x normal. That is the crossover.
Reality check (17 zones, 5 years): median worst spike ~1.43x. Even Winter Storm Uri only 1.28x. Portfolio worst days 1.3 to 1.9. Nothing near 3.
Caveat up front: holds for single-region emergencies. For storms hitting every region at once, nowhere clean to move anyway (that tests the lever, not robustness).
So robustness is an option you PRICE, not a free win. On observed grids it does not activate.""",

13: """[0:45] THE PLAYBOOK
A rule the operator uses tomorrow.
Layer 1 ALWAYS: schedule per region, day ahead. Riding the wave is free.
Layer 2 THE LEVER: add transfer. 4 to 10% off worst days, modest channel gets nearly all.
Layer 3 SKIP: co-movement models. Under 0.4%, below noise, while the wave dominates.
Layer 4 CONDITIONAL: buy robustness only if you face emergencies past a tripling. Real grids have not come close.
Every line measured, not asserted.""",

14: """[0:55] WHY YOU CAN TRUST A ZERO
[JUDGES: this + slide 10 is the crux for BOTH examiners. Nail power + positive control + equivalence.]
LOCKED FIRST: pass/fail rule in version control before reading 2025. Equivalence test turns 'found nothing' into a positive statement: any effect above 0.4% is RULED OUT, holds down to a 0.31% bar.
Corrected for multiple testing across all 144 cells, resampling that keeps nearby days together, re-ran on 2022/2023/2024. Same answer.
POWER: at 80% power it would detect any real gap down to 0.015 to 0.11%, an order of magnitude below the bar. Evidence of absence, not absence of evidence.
KEY: positive control. Flatten the wave, test fires at +1.46%. Real zero, not a blind instrument. Every number archived.""",

15: """[0:50] THE 202 TESTS
Same philosophy in code. 202 automated tests, 6 groups.
70 solve every scheduler on small problems with known answers (must match). 59 cover covariance/dependence tools. 25 enforce the shared rulebook (constraints). 16 check data pipelines (13 need licensed carbon files -> public build runs 189).
Proudest 11: the thesis's own MATH, run as tests every push; if a claim breaks, build goes red. 21 guard tests re-check headline numbers vs archived files.
Why so many? The weak point of a zero is 'you didn't look hard enough.' The tests prove we looked.""",

16: """[0:50] CONTRIBUTION
Two things, defended without inflation.
1. A RULE for when the dependence layer can pay: only when the ripple rivals the wave. Decomposition + a bound you can check before touching data + a measurement with a working positive control. A rule about a CLASS of problems, not one number.
2. A FAIR WAY to price a modelling layer: lock the rule first, keep everything identical, compare to like-for-like baseline + an economic bar. The field added this layer by default; we put a price on it.
Plus: measured transfer saving, priced robustness rule, a pipeline anyone can re-run.""",

17: """[0:45] LIMITATIONS (a limitation you name yourself is a strength)
One workload shape (splittable jobs, ramp limits); a very different cost structure could change the answer.
One main test year; re-runs agree but independent evidence is a few yearly reads, not 362 days. Longer eval is the named next step.
A pattern, not a law: we hand you the check, not a theorem.
Crossover characterized, not observed: a grid that crosses it flips the robustness verdict, and we say exactly where the line is.""",

18: """[0:35] CLOSE
The rule in one line.
Always schedule with the daily wave. Add the transfer channel (the lever, 4 to 10%). Skip co-movement models. Buy robustness only past a tripling, which real grids do not reach.
One sentence: a fancier model only pays when the ripple rivals the wave, and carbon grids are not there. Fancier is not safer. It is a bill, and now you know when it is worth paying.
Thank you. Happy to take questions.""",

19: """[BACKUP - jump if: 'how did you destroy the links?' / 'isn't the null a weak test?']
Falsification. Fit on real links; refit on a copy where each region keeps its OWN daily pattern but every cross-region link is shuffled out. Score both on worst days. Rule fixed in advance: if spatial structure matters, real-links must win.
It does not. Joint (filled) and shuffled (outline) schedules sit on top of each other. The wave, which the shuffle preserves, is what drives the schedule.""",

20: """[BACKUP - jump if: tail dependence / copulas]
Correlation sees only average, symmetric co-movement. A copula sees the whole shape, including whether regions hit extremes together. We measured tail dependence.
1. Asymmetric the WRONG way: regions hit CLEAN extremes together far more than dirty ones (CISO/LDWP 0.48 clean vs 0.25 dirty). A symmetric model can't represent this, and the co-movement sits in the clean tail a risk-averse scheduler ignores.
2. Re-ran under 4 couplings: independence, Gaussian, Clayton (lower-tail), comonotone (perfect). Comonotone is the CEILING over every copula: if even that buys nothing, no copula can. It bought under 0.2%, noise. That's why no elaborate vine copula was needed.""",

21: """[BACKUP - jump if: where do 144 cells / the numbers come from?]
144 = 4 grid-runs x 9 regime cells x 4 covariance estimators, every combination pre-committed; the multiple-testing correction applies to this family.
Biggest gap among 144: 0.355%, inside the band. Power to catch any real gap down to 0.015 to 0.11%.
54 extra rows = the instrument check: flatten the wave, fires at +1.46%, by design.
Claim is a conjunction, only as strong as the hardest case (Diversified), which still clears the bar at z=3.7.""",

22: """[BACKUP - jump if: is 0.4% arbitrary / tuned?]
No, and it cuts one way. 0.4% is the smallest saving that covers building+running a covariance layer, and that layer can HURT (up to 0.233% on Diversified).
Not tuned: conclusion holds for any bar down to 0.31%. Push it TIGHTER to 0.1% and only one cell flips (Diversified) to clearly negative, so a stricter bar makes 'skip' STRONGER.
Money: covariance channel ~$37k/yr, not reliably positive; transfer lever ~$1.7M.""",

23: """[BACKUP - jump if: 'no grid hits 3x but this zone hits 5x']
BPAT is a hydro zone with near-zero baseline carbon: a 5.12x jump on a tiny base is a small change in grams, barely moves the portfolio.
What risk actually feels is the portfolio worst day: Western 1.34x, Eastern 1.29x, Diversified 1.89x, all under a tripling.
Decisive check: draw emergencies from each region's own real worst days, robust plan still does not pay.""",

24: """[BACKUP - THE MATH SLIDE - jump if: 'walk me through your model / the constraints']
[JUDGES: Nacho can go deep on the Wasserstein/transport geometry. Point at the equation, then the constraints.]
OBJECTIVE, two parts. Pick schedule x (compute per region per hour). First part rho-bar . x = expected carbon bill (minimize alone -> pile into cleanest forecast hours). Second part epsilon x ||L^T x|| = caution surcharge; L is the sqrt of covariance, so it measures exposure to shared forecast swings. Epsilon = the caution dial; 0 -> plain LP, no statistics.
Covariance enters in EXACTLY ONE place, that second term = the entirety of Decision 2. SOCP, convex, exact optimum in seconds.
CONSTRAINTS: Ceiling (0 to capacity). Flexible split (fraction alpha inflexible, rest movable; alpha the master dial, swept 30/50/75%). Ramp (15 MW/h; kills the trivial dump-in-cleanest-hour solution). Deadline (>=20% flexible in the morning). Thermal/PUE (weather enters here, tightest). Transfer (budget Phi, Phi=0 honest baseline).
Removed on purpose: an aggregate power cap - it would have coupled regions artificially and faked the co-movement effect.
Calibrated to bind LOOSELY, schedule still moves 25-30%: best case for covariance, and still nothing.""",

25: """[BACKUP - jump if: 'what still needs to be done / future work?' - near-certain]
The null sharpened the agenda, did not close it. Four directions.
1. Settle the crossover: a calibrated outage model from grid-operator data (not the carbon tail), pre-committed, affine recourse; does real emergency risk ever reach 3x?
2. Make the null model-free: a copula-ambiguity Wasserstein DRO (Fan-Ji-Lejeune) on a fitted vine, robustifying the dependence structure itself. Mean-dominance predicts it still won't pay, but closes the last objection.
3. Transfer online and multistage: sequential forecasts, uncertain demand/transmission, ball on a learned forecast. Where the Diversified online loss could flip.
4. Generalize the rule into a condition for when cross-region dependence can ever help a robust allocation.
Plus external validity (longer eval, other generation mixes, hard deadlines). One line: the value, if any, comes from an active spatial decision, not a fancier passive model.""",
}


def main():
    prs = Presentation(str(DECK))
    n = len(prs.slides)
    for i, slide in enumerate(prs.slides, start=1):
        text = NOTES.get(i, "")
        slide.notes_slide.notes_text_frame.text = text
    # Write into the repo deck plus both Desktop copies (Marco is the one presented).
    targets = [
        DECK,
        DESKTOP / "Capstone_Defense_v2.pptx",
        DESKTOP / "Capstone_Defense_Marco.pptx",
    ]
    for t in targets:
        try:
            prs.save(str(t))
            print("wrote notes ->", t)
        except PermissionError:
            print("SKIPPED (open in PowerPoint, close it and re-run):", t)
    print(f"notes added to {sum(1 for i in range(1, n+1) if NOTES.get(i))} of {n} slides")


if __name__ == "__main__":
    main()
