# Healthcare manuscript final resubmission package

This self-contained package compiles the revised manuscript and reproduces its empirical, temporal-calibration, stochastic-programming, and randomized-simulation outputs. The original MDPI `Definitions` directory supplied with the submission is retained.

## Final manuscript

**Title:** *A Service-Constrained Two-Stage Stochastic Programming Framework for Hospital Pharmacy Medication Supply under Demand Uncertainty: Heterogeneous Demand, Conditional GARMA Scenarios, and Longitudinal Validation*

The clean MDPI compilation contains **29 pages, 10 manuscript tables, and 8 figures**. Table 1 positions the framework relative to prior literature; Tables 2–10 contain operational and analytical results. Substantive text added or changed in response to peer review is highlighted in red; retained/restored conceptual text remains black.

## Empirical architecture

- 13 anonymized medicines, 48 monthly requested-demand observations each.
- 12 expanding-window origins: 156 prospective medicine-month evaluations per policy.
- Marginal candidates: Normal, Gamma, NBII, ZINBI, and hurdle-NB, compared by training-window AIC.
- Full-series AIC differences below 0.01 are reported as numerical ties rather than arbitrary winners.
- Descriptive seasonality diagnostic: joint 12-month sine/cosine harmonic F-test after linear trend; with only four annual cycles it is not used to trigger a seasonal parametric branch. Seasonal-naive is retained prospectively.
- Training-only temporal screen: trend and lag-2 Ljung–Box diagnostics.
- Across 156 origins, temporal signal was detected in **82**, the Gaussian temporal branch was eligible in **72**, and a temporal model ultimately replaced the marginal generator in **46**; among those selections, GARMA was chosen in **19** and a trend GLM in **27**.
- Empirical stochastic program: service-constrained two-stage sample-average approximation (SAA), with **1,024** predictive scenarios per rolling decision.
- SC95: joint cycle-service/fill-rate floors of 0.95/0.95. SC99: 0.99/0.99.
- The unconstrained stochastic solution and newsvendor special case are diagnostic analytical references only.

## Main empirical results

- Central 90% held-out coverage: **84.0% -> 88.5%** overall after temporal adaptation; recurrent-positive **73.3% -> 83.3%**.
- SC95: fill rate **0.991**, cycle service **0.929**, mean cost **CLP 6.528 million**, SD cost **CLP 11.120 million** per medicine-month.
- SC99: fill rate **0.997**, cycle service **0.962**, mean cost **CLP 6.922 million**, SD cost **CLP 11.643 million**.
- Scenario-expected versus realized cost MAPE: **2.4%** for SC95 and **0.7%** for SC99.
- Full-series intermittent demand: seven of eight series show numerical AIC ties between ZINBI and hurdle-NB; M09 favors Normal. This is interpreted as evidence for zero-aware model structure, not superiority of one zero formulation.

## Diagnostic randomized simulation

The separate simulation isolates marginal statistical-fit versus unconstrained two-stage cost-loss divergence; it does not define the recommended hospital policy.

- **900** randomized cases.
- **48** fitting periods, **256 SAA scenarios per candidate fit**, and **12** future evaluation periods per case.
- **666 (74.0%)** operational ties within 1%; **234** unique operational winners.
- AIC/operational agreement among unique winners: **13.7%**.
- Mean/median AIC-selected cost regret: **2.19% / 0.11%**.
- Mean AIC-selected shortage rate **0.564**, overstock rate **0.317**, fill rate **0.436**.
- Exploratory independent tree: test accuracy **0.056**, balanced accuracy **0.213**. This very weak result is reported as negative screening evidence rather than a replacement for explicit optimization.

## Reproduce the analysis

```bash
python -m pip install -r requirements_revision.txt
python code/run_revision.py
```

The orchestrator runs the empirical stage, 12 deterministic simulation batches, output assembly, temporal-adaptive scenario calibration, and the fail-fast verifier.

Verify the supplied outputs without recomputation:

```bash
python code/02_verify_revision_outputs.py
```

## Compile the manuscript

```bash
latexmk -pdf manuscript_revised.tex
```

If `latexmk` is unavailable, use the standard `pdflatex` -> `bibtex` -> `pdflatex` -> `pdflatex` sequence.

## Interpretation boundary

Costs are model-based decision-sensitive nominal 2023 CLP comparisons, not audited hospital savings. Longitudinal monthly inventory position, lead times, pending orders, pack sizes, and medicine-level clinical criticality were unavailable and are not imputed. Both service constraints use the same predictive SAA scenario set; nominal service floors are therefore subject to out-of-sample calibration error. Multicenter prospective validation with richer inventory-state, supplier, lead-time, seasonality, and clinical-criticality data is required before prescriptive deployment.
