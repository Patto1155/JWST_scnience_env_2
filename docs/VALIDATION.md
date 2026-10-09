# Validation contract and reproducible audit

Run without FITS files, new data, API keys or the server:

```bash
python -m discovery.validation_audit \
  --output research_output/validation_audit.json \
  --report research_output/VALIDATION_AUDIT.md
```

The audit recomputes counts from `injection_recovery.json`'s per-source
`injections`. It never treats saved percentages as ground truth. The input
SHA-256 identifies precisely which trials were evaluated.

Every metric reports numerator, denominator, estimate and a 95% Wilson interval.
Zero trials are **not estimable**. Zero observed failures do not establish zero
failure probability. In the committed F444W faint unresolved trials, detection
and final acceptance are 27/119 (22.7%), while rejection is 0/27, whose 95% Wilson
upper bound is 12.5%. These describe different conditional populations.

Null classifier decisions are unknown rather than accepted. The audit reports
confirmed acceptance and bounds obtained by letting all unclassified detections
fail or pass. Binomial intervals assume independent trials; shared image noise,
batch environment, PSF and model systematics can invalidate that assumption.
These intervals are conditional diagnostic uncertainty, not a complete error
budget or an independently validated astrophysical selection function.

## Independent real-star / external-PSF contract

Supply `--external-validation path.json` to audit existing frozen predictions.
The JSON object contains `model_sha256`, `training_manifest_sha256`, a threshold
chosen before examining validation outcomes, and `training` / `validation` lists.
These digests declare provenance; the checker does not verify that an operator
actually scored those artifacts. Archive the corresponding model and training
manifest to permit independent reproduction.

Each row needs stable `source_id`, `sky_group_id`, `visit_id`, `field_id`, and
`sample_kind` (`real` or `synthetic`). Synthetic rows additionally need stable
`generator_id` and `psf_id`. Validation rows also need a binary `label` (0 real,
1 artifact), and a finite `artifact_score` in [0, 1]. Real-star truth should come
from external astrometry/spectroscopy or independently inspected repeat imaging,
never from the classifier being tested. Generator identifiers represent a code /
model family, not a different seed. PSF identifiers represent the calibration
source/model, not an arbitrary filename.

The independence gate forbids train/test overlap in any of those declared
identities. It deliberately enforces external field/visit and synthetic
generator/PSF separation; a random source split does not establish that contract.
Missing provenance is **unverified**, overlap is **failed**, and only complete
disjoint provenance is **passed**. Metrics are still diagnostic when the gate
fails, and the CLI returns exit status 2 to prevent an independent-validation
claim. A passed metadata gate alone does not establish trustworthy labels,
matched populations, or validated science performance.

A real-only stellar test estimates false rejection but cannot estimate artifact
recall or ROC AUC. AUC requires both real and artifact labels. Tied scores use
average ranks. Undefined metrics serialize as JSON null with explicit status,
never NaN. Add an independent artifact population for discrimination tests and
report its labeling limits, including possible transient contamination.

The legacy committed injections lack the necessary provenance. They remain
useful detector/classifier diagnostics, with independence explicitly unverified;
they are not retroactively upgraded to an external validation set.
