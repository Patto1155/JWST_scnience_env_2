# Southern holdout: frozen predictions, no outcomes opened

The 15 per-row catalogue covariates and predictions for both laws are frozen in
`research_output/flux_deficit_20261015/b_prediction.json` at `de5f430`, before
any new spectrum request. The input A models were frozen in original commit
`e2bc0c1` (integrated as `2c50154`). Minimum 15 usable paired log ratios,
object-bootstrap residual/intercept criteria, negative-fit handling, and the
paired squared-error law comparison are declared in the prediction file.

At 2026-10-15 04:59:22 UTC the first spectrum HEAD failed in the ordinary proxy
CONNECT tunnel with HTTP 403. No response body or spectrum was received, no GET
was made, and no retries or alternate endpoints were attempted. The receipt is
`research_output/flux_deficit_20261015/b_result.json`; its access-session marker
records one *attempt*, not an opened holdout. Successful spectrum opens: **zero**.
All 15 southern outcomes remain unopened. Body charge is **0 / 322,122,547 bytes**.

Neither law preference, holdout residual mean, nor holdout intercept was measured.
The training-only inverse-SNR intercept is -0.04228, object-bootstrap 95% CI
[-0.17408, 0.08923]. The inverse-SNR-squared intercept is -0.09227, CI
[-0.17879, -0.00811]. This model dependence cannot trigger a grey-offset
conclusion: B and C are not available, so their joint trigger is unresolved.
Arm D is deferred with zero acquisition, rather than closed on a demonstrated
zero intercept. No catalogue version, aperture/pathloss, continuum scale or
Jacobian cause has been excluded.

The one-shot CLI refuses an existing access marker. A future authorized-network
session must preserve this failed attempt, explicitly register a new session
receipt and review the unexecuted statistics implementation against the frozen
protocol before access. Do not delete the marker and silently retry.

Not run: 15 spectrum acquisitions/fits; holdout law comparison or bootstrap;
continuum/product-scale comparisons; D follow-up. Network denial is not an
archive-availability or scientific null result.
