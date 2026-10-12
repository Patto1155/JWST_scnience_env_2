# Research5 final validation

The final local software gate passes **767 tests with three explicit skips**
(770 collected, no failures or errors). The exact interpreter is
`/tmp/jwst-handover-env/bin/python`, Python 3.12.14; all 65 distributions in
`requirements-research.lock` match. Four BLAS thread limits were set to one.
GOODS-N outcomes remain unopened.

`research_output/research5_final_validation.json` records the complete configured
`scripts/quality_gate.py` run, full pytest results, source hashes before and
after the run, exact commands, skip reasons and evidence hashes. Configured lint,
formatting and type checks passed. Direct strict lint and formatting cover all
20 new Research5 Python modules and test files present at the freeze. Hash
snapshots do not imply every scientific script was executed by pytest;
independent numerical receipts separately delimit actual-data analyses.

## Formatting repair and retained evidence

The first direct Research5 formatting check identified two SPHEREx reviewer
files. The owner ran the locked formatter on those files only. The captured
pre-format hashes match the full-suite snapshot, and complete Python ASTs are
identical before and after formatting. Strict lint and formatting were then
rerun successfully. The full suite was not repeated for this formatting-only
change. The initial formatting failure remains in the receipt and original
log; final code hashes and the repair proof are recorded separately.

Retained compressed evidence:

- `research5_final_quality.log.gz`: configured gate, full suite and initial
  direct checks, including the formatting failure.
- `research5_final_tests.xml.gz`: the full-suite JUnit evidence.
- `research5_final_format_repair.log.gz`: successful final strict lint and
  formatting checks after the AST-identical repair.

No Python source changed during the full gate. The two documented formatting
files are the only source differences afterward.

## Missing inputs and scientific scope

Two skipped JWST visual integration tests require the separately provisioned
original imaging archive. The third skip requires the independently pinned
author Cue weights through `JWST_CUE_ARCHIVE`. These skips do not validate those
absent inputs. This gate did not restore original JWST exposures or rerun the
Cloudy thermal solver.

The scientific claims remain independently scoped: frozen optical and original
spectral confirmation gates that failed remain failed; subsequently authorized
extensions are exploratory. The stellar review retains a conditional TESS
amplitude baseline without a physical evolution detection. SPHEREx narrow-channel
measurements do not supply the missing full W1 response or independent visits.
Software success does not establish a new astrophysical discovery.

## Publication input linkage

The read-only final audit is
`research_output/research5_final_artifact_bindings.json`. It verifies all
**88 file pins** in `research5_time_binding.json`, all eleven final SPHEREx
compressed and decompressed cutout hashes and their acquisition receipts, and
the current independent-review code/result pins. The published trimmed
SPHEREx `000` file is bound to its final measurement and receipt. No mismatches
were found. Stellar author and independent-review validation pins also match
the current files.

These checks support release of the current artifacts under their documented
exploratory, conditional and stopped-pilot limits. A change to code, inputs or
claims requires the corresponding evidence to be refreshed.
