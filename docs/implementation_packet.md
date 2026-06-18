I now have the complete ground truth. I have everything I need to merge the six reviews into one ruthless, paste-ready implementation packet. Let me write it.

---

# IMPLEMENTATION PACKET — capstone_thesis.tex value-first pivot

**Source of truth:** I read all 1730 lines of `thesis/capstone_thesis.tex`, plus `docs/thesis_change_map.md` and `docs/pivot_plan.md`. Line numbers below are verified against the actual file. The six section reviews were drafted against the real file and are largely sound; I corrected three places where reviewers invented section labels/numbers that don't exist (`\ref{sec:res-phase3}`, `\ref{sec:res-mech}` is real, `\ref{sec:res-scheduler}` is not), cited the wrong Yaxin mechanism, or assumed re-runs that haven't happened yet. Those are flagged in Part 4.

---

## PART 0 — DO THESE TWO THINGS BEFORE YOU TOUCH THE .TEX (human, blocking)

Per `pivot_plan.md` M6 + M5, these are async and gate the rest. The whole packet below is wasted if they come back wrong.

1. **M6 — Bissan sign-off.** Email the one-paragraph new spine + `thesis_change_map.md`. Do not start the 20h rewrite until he confirms the value-first frame.
2. **M5 — Yaxin attribution.** Email Yaxin + Bissan to confirm the boundary: Yaxin owns deterministic transfer; Marco owns the robust/stochastic transfer layer + the crossover. **The exact savings attribution language below assumes she confirms.** If she disputes the boundary, every "Yaxin"/`yaxin2026` reference in this packet must change.

---

## PART 1 — ORDERED MECHANICAL EDIT LIST (high-confidence, paste-ready)

Apply **bottom-to-top** (highest line number first) so earlier edits don't shift later line numbers. I've ordered them top-to-bottom for reading but marked each with its line range; execute in reverse.

### EDIT 1 — Title (lines 51–54)
**Replace:**
```latex
{\Large\bfseries Does Spatial Correlation of Carbon Intensity Improve\par
Distributionally Robust Carbon-Aware Data-Center Scheduling?\par}
\vspace{0.5cm}
{\large A Multi-Grid Falsification Study with a Causal Mechanism\par}
```
**With:**
```latex
{\Large\bfseries The Price of Sophistication: When Do Spatial and\par
Robust Modeling Pay in Carbon-Aware Data-Center Scheduling?\par}
\vspace{0.5cm}
{\large A Day-Ahead Migration Scheduler and a Complexity--Value Decision Rule\par}
```

### EDIT 2 — Abstract (lines 74–100)
**Replace the entire `abstract` environment body** (everything between `\begin{abstract}` line 74 and `\end{abstract}` line 100) with:
```latex
\noindent Data-center operators can shift compute toward cleaner hours and regions,
and recent work applies distributionally robust optimization (DRO) to carbon-aware
scheduling. The unexamined question is which modeling layers actually pay for their
complexity. This thesis builds a working day-ahead carbon-aware migration scheduler
and characterizes the value of each layer.

Over the honest baseline---carbon-aware scheduling with no inter-region transfer
($\Phi=0$), on the same feasible set---active migration saves $4.7$--$10.1\%$ of
daily $\CVaR_{0.95}$ emissions, an $8$--$11$ percentage-point spatial lever. This
deterministic transfer channel is the dominant lever, and the carbon-computing
literature independently finds spatial shifting dominates temporal shifting. We then
isolate the value of \emph{passive} sophistication. Using a Mahalanobis--Wasserstein
DRO solved as a second-order cone program, a pre-registered shuffled-marginals
falsification test across three real US/Canada grids spanning the dependence spectrum
(US West, an Ontario-anchored Eastern belt, an engineered solar/wind/hydro portfolio),
with an Iberia--France anchor, returns a replicated null: encoding spatial covariance
adds below $0.4\%$ of $\CVaR$, surviving Ledoit--Wolf shrinkage, residualization,
Benjamini--Hochberg correction, walk-forward validation, and a per-cell equivalence
test. A mean-ablation shows the covariance signal is genuine but masked by the mean
field (Proposition~1), and a tail-dependence analysis shows the residual dependence
is non-elliptical and upper-tail independent, hence invisible to covariance-based
ambiguity sets; a one-paragraph copula appendix confirms even the maximal coupling
recovers nothing.

Finally we ask when robustness itself pays. Following Bertsimas and Sim's price of
robustness, a DRO over day-ahead forecast error buys a small worst-day (CVaR) tail
reduction at a mean premium, with a value of the stochastic solution near zero, and
pays over deterministic transfer only past an emergency-severity crossover
$M^\star\approx3$. Tested against real data-grounded worst-tail emergencies across
17 zones, that crossover never activates. The thesis contributes (i)~a working
scheduler with honest savings, (ii)~a screening rule for when passive dependence
modeling fails, and (iii)~a price-of-robustness decision rule with a tested,
data-grounded bound---all under 194 unit tests and pre-registration.
```
*Honesty guard:* abstract says "$4.7$--$10.1\%$ of $\CVaR$ = $8$--$11$ pp lever" and **never** says "12–16% vs carbon-blind." Good per M1.

### EDIT 3 — Research questions (lines 142–151)
**Replace** the `description` block with:
```latex
\begin{description}[leftmargin=1.4em,itemsep=2pt]
\item[RQ1.] How much can a day-ahead carbon-aware migration scheduler cut daily
$\CVaR_{0.95}$ emissions relative to carbon-aware scheduling without inter-region
transfer, and which lever drives the saving?
\item[RQ2.] When does adding passive modeling complexity---spatial covariance, or a
non-elliptical copula---improve out-of-sample tail emissions, and at what cost?
\item[RQ3.] When does robustifying against day-ahead forecast error pay over
deterministic transfer, and do real grids ever reach that regime? What decision rule
follows?
\end{description}
```

### EDIT 4 — Contributions (lines 153–170)
**Replace** the `\subsection{Contributions}` body with:
```latex
\subsection{Contributions}
The thesis makes four contributions. (i)~\emph{A working day-ahead scheduler with
honest savings}: active inter-region migration cuts out-of-sample $\CVaR_{0.95}$ by
$4.7$--$10.1\%$ ($8$--$11$ percentage points) over the carbon-aware no-transfer
baseline ($\Phi=0$, same feasible set) across three real grids; the deterministic
transfer lever is dominant. The deterministic-transfer savings are joint work with
collaborator Yaxin Li~\citep{yaxin2026}, who owns the deterministic transfer
algorithm; this thesis owns the robust/stochastic transfer layer and the crossover.
(ii)~\emph{A screening rule}: a pre-registered shuffled-marginals falsification test
and mean-ablation diagnostic isolate the value of spatial covariance, yielding a
replicated null (gaps below $0.4\%$ of $\CVaR$, robust to estimator choice,
multiple-testing correction, and walk-forward), with Proposition~\ref{prop:meandom}
(mean-dominance) as the a-priori certificate of when passive dependence modeling
cannot help. (iii)~\emph{A price-of-robustness decision rule}: framing robustness as
a complexity--value trade-off (following Bertsimas \& Sim), the DRO over day-ahead
forecast error buys tail reduction at a mean premium and pays only past an
emergency-severity crossover $M^\star\approx3$ that real data-grounded emergencies
across 17 zones never reach. (iv)~\emph{A reproducible pipeline}: version-controlled,
CI-tested (194 unit tests), pre-registered, with archived license-safe summary tables
for every reported number.
```

### EDIT 5 — Thesis structure (lines 172–180)
**Replace** the `\subsection{Thesis structure}` body with:
```latex
\subsection{Thesis structure}
Section~\ref{sec:lit} reviews the carbon-aware scheduling and DRO literature and
locates the gap: the value of modeling sophistication has been assumed, not measured.
Section~\ref{sec:method} develops the day-ahead migration scheduler, the
Mahalanobis--Wasserstein DRO over forecast error, the shuffled-marginals falsification
test, and the pre-registered protocol. Section~\ref{sec:results} reports the honest
savings and the transfer lever, the screening rule (the replicated spatial null with
its robustness battery and mean-ablation), and the price-of-robustness crossover.
Section~\ref{sec:discussion} interprets the findings, gives the practitioner decision
rule, and states the honest limitations. Section~\ref{sec:conclusion} concludes.
Phase~2 copula models are demoted to Appendix~\ref{app:copula}.
```

### EDIT 6 — Copula demotion: lit review (lines 215–233)
The lit review has the copula/Fan material in two subsections. **Trim, don't delete** (Bissan #4: he doesn't get *where it came from* — so reduce prominence, keep one sentence + the Bertsimas anchor).

**6a — Replace lines 215–218** (the Fan et al. "robustifies the dependence structure" sentences at the end of §2.2):
```latex
However, robustification is not free. Bertsimas and Sim~\citep{bertsimas2004}, in
\emph{The Price of Robustness}, frame the trade-off: as the ambiguity set grows the
nominal objective worsens monotonically, so the operative question is not whether
robustness helps but \emph{when} its tail protection justifies the mean premium.
This is the complexity--value lens of the present study.
```

**6b — Replace the entire §2.3 "Spatial dependence and its modelling" (lines 220–233)** with a shorter version that demotes copula detail to corroboration:
```latex
\subsection{Modeling cross-region dependence}
Cross-region dependence enters a Mahalanobis--Wasserstein model only through the
off-diagonal covariance blocks. Estimating large covariance matrices from short
panels is noisy; shrinkage estimators \citep{ledoit2004} are the standard remedy and
serve here as a robustness arm. Beyond second moments, dependence is fully described
by the copula \citep{sklar1959,joe2014}, and the Gaussian copula has zero asymptotic
tail dependence for any correlation below one \citep{embrechts2002}---a property we
use as a diagnostic benchmark. Whether richer non-elliptical structure (e.g.\ vine
copulas \citep{aas2009}, or copula-ambiguity DRO \citep{fan2024}) improves a
\emph{stochastic program} depends on whether it changes the optimal decision
out-of-sample; we test this directly and report it in Appendix~\ref{app:copula}.
```
*Add a `\bibitem{bertsimas2004}` — see Part 4, item C.*

### EDIT 7 — Yaxin attribution in Annex A (lines 1698–1722)
**Replace lines 1698–1700** (the "sole author... responsible for all components" opener):
```latex
This Research Capstone was completed by \textbf{Marco Ortiz Togashi} under the
supervision of Prof.\ Bissan Ghaddar, with the deterministic inter-region transfer
component developed jointly with collaborator \textbf{Yaxin Li}. Responsibilities:
```
**Then add a new bullet** after the "Modelling" item (insert after line 1709):
```latex
\item \textbf{Attribution boundary.} The \emph{deterministic} inter-region transfer
algorithm and its operational-constraint integration are Yaxin Li's work
\citep{yaxin2026}; the deterministic-transfer savings (Section~\ref{sec:res-transfer})
are reported as joint results. This thesis owns the \emph{stochastic/robust} transfer
layer (one-shot and two-stage robust commitment), the day-ahead forecast-error DRO,
and the tail-risk crossover and decision rule.
```
**Replace** the final orphan sentence (lines 1720–1722, "The inter-region transfer-channel proposal... pending supervisor coordination.") with:
```latex
The deterministic transfer channel overlaps Yaxin Li's scope and is attributed to her
throughout; the robust extension and crossover are the author's own.
```

---

## PART 2 — DRAFTED NEW CONTENT FOR RESTRUCTURED SECTIONS (paste-ready)

### 2A — Methodology: re-point the DRO to day-ahead forecast error (lines 266–290)
This is M4, the pivotal change. **Replace the `\subsection{Distributionally robust formulation}` preamble (lines 266–270)** with:
```latex
\subsection{Distributionally robust formulation: day-ahead forecast-error hedging}
The robust layer hedges \emph{tomorrow's forecast error}, not a static multi-year
distribution. On each day the scheduler commits against a day-ahead point forecast
$\bar\rho$ of the carbon field; the realized field departs from it by a residual
whose empirical distribution $\hat{\mathbb P}$ (forecast actuals minus forecast,
pooled over the training window) defines the ambiguity. We minimize worst-case
expected emissions over a type-2 Wasserstein ball $\mathcal B_\varepsilon(\hat{\mathbb
P})$ of radius $\varepsilon$ centred on that residual distribution, with Mahalanobis
ground metric induced by the empirical residual covariance $\hat\Sigma\in\R^{RT\times
RT}$:
```
Keep equations (1)–(2) (lines 271–290) **unchanged** but relabel one clause: at line 280, change "where $\bar\rho$ is the empirical mean field" to "where $\bar\rho$ is the day-ahead point forecast." Everything downstream (Cholesky, SOCP, CLARABEL) is identical — the math doesn't change, only what $\hat\Sigma$ and $\bar\rho$ *mean*. This is the cheap, honest version of M4.

**Add one paragraph in §3.6 Data (after line 515)** describing the forecast baseline:
```latex
\paragraph{Day-ahead forecast and residuals.} The robust layer's ambiguity set is
built on day-ahead forecast residuals. The point forecast $\bar\rho$ is the
hour-of-day climatological mean on the training window (a persistence-class baseline);
residuals $\rho_{\mathrm{actual}}-\bar\rho$ furnish $\hat\Sigma$. This makes the DRO's
job operationally concrete---hedging the 24-hour-ahead forecast miss---rather than
year-to-year distribution shift.
```

### 2B — Methodology: demote falsification framing + copula subsection
- **Reframe falsification opening (line 430–431):** change "The test is a falsification: it is built to detect a spatial benefit if one exists, so a null is informative." to:
```latex
The test is the screening tool of this thesis: built to detect a spatial benefit if
one exists, it isolates the \emph{value} of passive covariance from the \emph{validity}
of spatial correlation, and validates Proposition~\ref{prop:meandom}'s prediction.
```
- **Phase 2 copula subsection (lines 548–623):** This is two algorithms + ~75 lines. Per M4/Bissan #4, **cut from main methodology**. Replace lines 548–623 with one redirect sentence:
```latex
\subsection{Phase 2: richer dependence models (summary)}\label{sec:method-copula}
The covariance ball represents only \emph{elliptical} dependence. To foreclose the
``wrong object'' objection, Appendix~\ref{app:copula} re-runs the falsification with
Gaussian, lower-tail Clayton, and the maximal (comonotone) copula, fitted to the
empirical rank structure. The result confirms the screening rule and is summarized in
one paragraph there; the mean-dominance bound below explains why it must hold.
```
- **Keep** lines 625–694 (Prop 1 + mean-dominance bound) entirely — promote in narration. Tail-dependence diagnostic methodology (lines 539–546) stays.

### 2C — Results: NEW §4.1 day-ahead savings + transfer lever (insert before line 769)
Insert this **new subsection after the RQ1 correlation block (after line 767, before §4.2 line 769)**. *This depends on the M1 re-run (Part 4, item A) producing the snapshot; the numbers below are the audited $4.7$–$10.1\%$ / $8$–$11$pp figures from `pivot_plan.md`.*
```latex
\subsection{The day-ahead scheduler and its savings (RQ1)}\label{sec:res-transfer}
The scheduler migrates compute across regions against a day-ahead forecast. We report
out-of-sample $\CVaR_{0.95}$ under two honest comparators on the \emph{same} feasible
set: \textbf{carbon-blind} (schedule ignores carbon); and \textbf{carbon-aware,
no transfer} ($\Phi=0$), each region scheduled by its own forecast with no
inter-region flow. The transfer arm adds inter-region flows $f_{r\to s,t}\ge0$ under a
budget $\Phi$.

Figure~\ref{fig:transfercurve} reports the saving against $\Phi$. Active transfer cuts
out-of-sample $\CVaR_{0.95}$ by \textbf{$4.7$--$10.1\%$} relative to the $\Phi=0$
baseline across the three grids---an $8$--$11$ percentage-point spatial lever. The
lever is the spatial \emph{mean}: at each hour one region is cleanest on average, and
migration ships work there. The saving is \emph{deterministic}, captured without any
dependence model; the deterministic transfer algorithm is Yaxin Li's
work~\citep{yaxin2026}, integrated here. This is consistent with the carbon-computing
literature, which finds spatial shifting dominates temporal shifting
\citep{wiesner2021,radovanovic2022}. We deliberately report the saving over the
$\Phi=0$ carbon-aware baseline, not over a uniform spread: the honest lever is
transfer-vs-no-transfer, not a strawman.

\begin{figure}[t]
\centering
\includegraphics[width=0.92\textwidth]{../figures/transfer_value_curve.pdf}
\caption{The transfer lever. Out-of-sample $\CVaR_{0.95}$ saving against the
inter-region transfer budget $\Phi$, relative to the carbon-aware no-transfer
baseline ($\Phi=0$, dashed reference). Active migration captures the $8$--$11$
percentage-point spatial lever; the curve saturates as the feasible mean-based gain
is exhausted. Deterministic transfer (Yaxin Li); robust layer added in
Section~\ref{sec:res-crossover}.}
\label{fig:transfercurve}
\end{figure}
```
**Also add the complexity-frontier figure** as the chapter opener (the centerpiece per the brief). Insert immediately after the new subsection above:
```latex
Figure~\ref{fig:frontier} places every model class on a single complexity--value
frontier (carbon-blind $\to$ deterministic per-region $\to$ robust per-region $\to$
deterministic transfer $\to$ robust transfer). Deterministic transfer dominates the
frontier; passive covariance and copula layers add no height; robust transfer pays
only in the tail (Section~\ref{sec:res-crossover}).

\begin{figure}[t]
\centering
\includegraphics[width=0.85\textwidth]{../figures/complexity_frontier.pdf}
\caption{The complexity--value frontier. Out-of-sample $\CVaR_{0.95}$ saving (vs
carbon-blind) against modeling/estimation complexity. The value lives in
deterministic transfer; passive dependence sophistication is flat; robust transfer is
conditional on tail severity.}
\label{fig:frontier}
\end{figure}
```

### 2D — Results: promote the crossover into main body as NEW §4.6 (M3)
Insert **after the Phase 2 results subsection ends (after line 1258), before Discussion (line 1260)**. This lifts the honest content of Appendix B into the graded body. *Note the honesty bound is the TESTED data-grounded result, with the dirty-grid ceiling as a supporting note only — per the brief's honesty bound.*
```latex
\subsection{The price of robustness: when does the crossover pay?
(RQ3)}\label{sec:res-crossover}
Passive sophistication adds nothing under nominal conditions. The honest question the
title poses is when \emph{robustness} pays. We make the spatial structure an active
decision (inter-region flows) and add a two-stage robust commitment with
migration-limited recourse, hedging day-ahead forecast error. By Proposition~1's
logic the mean dominates under nominal carbon, and indeed robust $\approx$
deterministic there (the value of the stochastic solution is near zero; the DRO buys
no mean reduction---a price-of-robustness result, not an emissions win).

Robustness earns its keep only in the tail. Modeling rare grid-emergency events (with
probability $0.1$/day a region's carbon scales by severity $M$), the robust
commitment's advantage over the risk-neutral one grows with $M$: zero at $M=1$,
crossing positive near $M^\star\approx3$, reaching $+8.4\%$ of $\CVaR_{0.95}$ at $M=4$
on the US West (Figure~\ref{fig:crossover}). The robust schedule stays hedged while
the risk-neutral one is burned when its favored region spikes.

\paragraph{Honest bound: real grids stay below the crossover.} We tested
data-grounded worst-tail emergencies across all 17 zones (US West, Eastern
Interconnection, Iberia--France, Canada). The worst realized joint-tail severity
reaches only $M\approx1.4$, well below $M^\star$, so on real historical data the
crossover does \emph{not} activate: the robust layer's promised value is real but
unrealized. We resist a clean ``carbon ceiling makes robustness impossible'' theorem:
clean grids spike \emph{relatively} large (BPAT $5\times$, Ontario $2.6\times$
clean-to-dirty), so a ceiling argument bounds only dirty grids. The rigorous claim is
the tested one---across the zones we have, $M$ never reaches $M^\star$---with the
dirty-grid ceiling as a supporting note, not a universal proof.

\begin{figure}[t]
\centering
\includegraphics[width=0.8\textwidth]{../figures/crossover.pdf}
\caption{The price-of-robustness crossover. Robust-minus-risk-neutral
$\CVaR_{0.95}$ advantage against emergency severity $M$. The crossover is
$M^\star\approx3$; tested real grids (17 zones) peak at $M\approx1.4$
(Figure~\ref{fig:allzones}), so robustness does not activate on observed data. Rule:
deploy deterministic transfer; robustify only if you expect $M>M^\star$.}
\label{fig:crossover}
\end{figure}

\begin{figure}[t]
\centering
\includegraphics[width=\textwidth]{../figures/all_zones_correlation.pdf}
\caption{Worst realized joint-tail severity across 17 zones (2025 test year). All
tested grids stay below $M^\star\approx3$, grounding the honest verdict that
robustness adds no value under observed conditions.}
\label{fig:allzones}
\end{figure}
```
**Then collapse Appendix B (lines 1608–1693):** keep the "Implementation and validation" paragraph (1662–1676, the unit-test invariants — that's real rigor) and the five-part roadmap (1678–1693) as future work; **delete the now-duplicated findings** (lines 1616–1660) and replace with a one-line pointer: "The findings summarized in Section~\ref{sec:res-crossover} rest on this validated module; what remains preliminary is the emergency-model calibration and pre-registration, not the optimization."

### 2E — Discussion + Conclusions: the decision rule (M3/S3)
**Replace the `\subsection{Practical recommendation}` (lines 1321–1340)** with a layered decision rule:
```latex
\subsection{The decision rule: when does each layer pay?}\label{sec:practical}
The findings compose into a practitioner rule. \textbf{Layer 1 (deploy always):}
day-ahead carbon-aware per-region scheduling. \textbf{Layer 2 (deploy if migration
bandwidth exists):} deterministic inter-region transfer, the dominant lever
($4.7$--$10.1\%$, $8$--$11$ pp; Section~\ref{sec:res-transfer}); this needs accurate
per-region mean forecasts and transfer-capacity planning, not dependence estimation.
\textbf{Layer 3 (skip):} spatial covariance or copula modeling---genuine but masked by
the mean field (Proposition~\ref{prop:meandom}), it adds below $0.4\%$ and is mildly
counterproductive in the diversification-friendly case. \textbf{Layer 4 (conditional):}
robustify the transfer against forecast error only if emergency severity realistically
exceeds $M^\star\approx3$; across the 17 real grids we tested it did not, so
deterministic transfer was unambiguously dominant. The robust layer is a tail-risk
option for operators with a concrete emergency prior, stated upfront.

In absolute terms, on the Eastern US--Canada facility ($\approx160$ MW,
$\approx460{,}000\,\text{tCO}_2$/yr), the transfer lever is worth on the order of
$\$1.7$M/yr at $\$80/\text{tCO}_2$, while the spatial-covariance channel is
$\approx\$37{,}000$/yr and not reliably positive. The value worth pursuing lives in
the transfer decision and the mean forecast, not the second moment.
```
**Replace Conclusions §6.1 "Answers to the research questions" (lines 1372–1408)** to lead value-first. Keep the existing RQ-answer prose but re-map to the new RQs:
```latex
\subsection{Answers to the research questions}
\textbf{RQ1, how much does the scheduler save, and which lever?} Active inter-region
migration cuts out-of-sample $\CVaR_{0.95}$ by $4.7$--$10.1\%$ ($8$--$11$ pp) over the
carbon-aware no-transfer baseline across three real grids; the deterministic transfer
lever dominates and the saving is mean-driven (Section~\ref{sec:res-transfer}),
consistent with spatial $>$ temporal shifting in the literature.

\textbf{RQ2, does passive dependence modeling help?} No. Across the dependence
spectrum the spatial gap stays below $0.4\%$ of $\CVaR_{0.95}$, is not sign-stable,
and survives shrinkage, residualization, Benjamini--Hochberg over 144 cells,
walk-forward, the full $\CVaR_{0.90}$--$\CVaR_{0.99}$ range, and a per-cell
equivalence test---with the DRO genuinely engaged ($\varepsilon^\star=1$). A
mean-ablation shows the signal is real ($+1.46\%$ in a covariance-only world) but
masked; tail dependence is non-elliptical and upper-tail independent; the copula
appendix confirms even maximal coupling recovers nothing. Proposition~1 (mean-dominance)
is the screening rule that predicts all of this.

\textbf{RQ3, when does robustness pay?} Only in the tail. The robust transfer layer
buys CVaR tail reduction at a mean premium (value of the stochastic solution $\approx
0$) and beats deterministic transfer only past $M^\star\approx3$. Tested against real
worst-tail emergencies across 17 zones ($M_{\max}\approx1.4$), the crossover never
activates: robustness has a characterized but, on observed grids, empty domain of
value.
```
**Keep** §6.2 Contributions and §6.3 Future work largely as-is but delete the "pending supervisor sign-off / collaborator's scope" hedge from line 1454–1455 (now handled by the Yaxin attribution in §4.1 + Annex A).

---

## PART 3 — WHAT TO MAKE BETTER (top 5, ranked for June 29)

1. **Do the M1 baseline re-run before writing a single Results number (BLOCKING, integrity).** `pivot_plan.md` says `run_dayahead_savings.py` / `run_transfer_value_curve.py` currently compare vs a *uniform spread*, and `greedy_sort_schedule_multiregion` ignores ramp/thermal. Until you re-run with the $\Phi=0$ rolling baseline on the *same* feasible set and re-snapshot, the $4.7$–$10.1\%$ / $8$–$11$pp headline is not yet earned. Every §4.1 number is a placeholder until that snapshot exists. ~2–3h. **This is the single thing that sinks the defense if skipped.**

2. **Resolve the $M^\star$ honesty bound precisely.** The brief is explicit: do NOT claim a clean "carbon ceiling makes it impossible" theorem; the rigorous claim is the *tested* 17-zone result ($M_{\max}\approx1.4 < M^\star\approx3$), with the dirty-grid ceiling as a supporting note only. My §4.6 draft does this, but the *figure* `all_zones_correlation.pdf` must actually plot realized severity per zone (not correlation) — verify the figure shows what the caption claims, or relabel.

3. **Make the complexity frontier the literal centerpiece.** It's the brief's named centerpiece but currently has no home. Put `complexity_frontier.pdf` at the head of §4 (my 2C draft does), and make sure its y-axis is the *honest* saving (vs $\Phi=0$ and vs carbon-blind both shown), not a strawman. One figure that lands the whole thesis.

4. **Page budget: you are cutting net, which is good — verify 30pp.** Demoting copula (Phase 2 methodology ~75 lines + results condensed) and collapsing Appendix B duplicated findings frees space; the new §4.1, §4.6, and decision rule add it back. Build the PDF and check `\pageref`-style page count *excluding* refs/appendices. If over, the copula appendix and the Phase 3 roadmap (Parts 4–5) are the first to trim.

5. **Reference + label hygiene (cheap, high-risk if wrong).** Add `\bibitem{bertsimas2004}` and `\bibitem{yaxin2026}` (Part 4). Several section reviewers cited labels that don't exist (`\ref{sec:res-phase3}`, `\ref{sec:res-scheduler}`, `\ref{sec:rule}`, `app:emergencies`). I reused only real labels (`sec:res-transfer` is new and consistent; `sec:res-crossover` is new; `app:copula` is new). Grep all `\ref`/`\label` after editing and compile twice — a dangling ref prints `??` and looks unfinished to Bissan.

---

## PART 4 — NEEDS MARCO'S HUMAN JUDGMENT (flagged explicitly)

**A. The M1 re-run and its numbers (BLOCKING).** I cannot run `run_transfer_value_curve.py`. The $4.7$–$10.1\%$ / $8$–$11$pp figures come from `pivot_plan.md` and your existing Conclusions line 1450. **Confirm these survive the honest-baseline re-run** before pasting §4.1. If they shift, update §4.1, the abstract, contributions, and the decision rule together (they all repeat the number).

**B. Yaxin citation `yaxin2026` (BLOCKING on her email).** I inserted `\citep{yaxin2026}` in three places (Contributions, §4.1, Annex A). You must (i) get her sign-off on the boundary, and (ii) give me/the file the real bib entry — is it a thesis, a co-authored note, an internal report? Until then `yaxin2026` is a dangling cite. If she declines co-attribution, the "joint results" framing must soften to "uses a deterministic transfer formulation developed in parallel by a collaborator."

**C. Two bib entries to add** (before `\end{thebibliography}`, line 1531). Bertsimas is canonical and safe; Yaxin needs your input:
```latex
\bibitem{bertsimas2004} D.~Bertsimas and M.~Sim, ``The price of robustness,''
\emph{Oper. Res.}, vol.~52, no.~1, pp.~35--53, 2004.
\bibitem{yaxin2026} Y.~Li, ``[TITLE -- Marco to supply],'' IE University Research
Capstone, 2026.
```

**D. DRO re-pointing — narration vs re-computation.** My 2A draft re-points the DRO to day-ahead forecast error by **relabeling** $\hat\Sigma$/$\bar\rho$ as residual covariance / day-ahead forecast, *without re-deriving results*. This is honest **only if** your $\hat\Sigma$ in the code is in fact built from forecast residuals (or the climatological-mean residual I describe in the new Data paragraph). **Verify what the pipeline actually feeds the SOCP.** If it currently uses raw multi-year covariance, you either (i) re-run with residual covariance (cleaner, costs compute), or (ii) narrow the claim to "covariance of de-seasonalized residuals," which §3.7 already computes. Do not claim day-ahead if the code is yearly — that's exactly Bissan #2/#3.

**E. "17 zones" and "$M_{\max}\approx1.4$" provenance.** The crossover §4.6 hard-codes 17 zones and a $1.4$ worst severity. Confirm these come from a real snapshot (the `all_zones_correlation` / `part3_real_emergency` figures suggest they do) and not from a section reviewer's guess. The honesty of the whole RQ3 answer rests on this number being real and tested.

**F. Tone on Phase 2/copula.** I demoted it to one appendix paragraph (Bissan #4). But you spent real effort there and it *is* rigorous corroboration. Judgment call: if Bissan in the M6 reply signals he wants it *gone* entirely vs *minimized*, adjust. My draft minimizes (keeps the appendix); going further (delete) loses the "even the maximal copula recovers nothing" closer that strengthens the screening rule.

**G. Don't over-rotate the abstract's DRO honesty.** The abstract now says VSS $\approx 0$ and "never activates." That is maximally honest and defensible per the brief — but read it once more in Bissan's voice: it must read as "characterized bounded domain of value" (a contribution), not "the DRO failed" (a second null). My phrasing aims for the former; you're the judge of whether it lands.