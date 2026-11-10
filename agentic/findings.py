"""What the thesis found, in one place for the MCP resource and the A2A answers."""

FINDINGS = {
    "RQ1": "Moving work between regions pays: 4.0-9.9% lower out-of-sample CVaR_0.95 than no transfer.",
    "RQ2": "Modelling how regions co-move (covariance, copulas) adds under 0.4% of CVaR.",
    "RQ3": "Distributionally robust hedging pays only above an emergency severity of about 3x; "
           "real joint-grid severities are 1.29-1.89x.",
    "recommendation": "A per-region scheduler plus an active transfer channel captures the value; richer "
                      "dependence models and robustness are conditional options.",
}
