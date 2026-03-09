# Research Report

This run built a masked Universe Table from registered JWST datasets and applied source-level dropout screening.

## Key Findings
- Catalogued 150 datasets across programs (JADES 1180, CEERS 1345, SMACS 2736).
- High-z source candidates: 1732 flagged by source-level F090W/F444W dropouts.
- Review shortlist: 25 highest-scoring candidates after falsification-aware triage.
- Anomaly flags: 55 statistical outliers/non-Gaussian tails.

### Visual evidence products
- GS-MEDIUM-HST: overview=research_output\visuals\GS-MEDIUM-HST_field_field_overview.png, segmentation=research_output\source_catalogs\GS-MEDIUM-HST_sources_segmentation.png, colors=research_output\visuals\GS-MEDIUM-HST_color_diagnostic.png, shortlist=6
- SMACS-J0723.3-7327: overview=research_output\visuals\SMACS-J0723.3-7327_field_field_overview.png, segmentation=research_output\source_catalogs\SMACS-J0723.3-7327_sources_segmentation.png, colors=research_output\visuals\SMACS-J0723.3-7327_color_diagnostic.png, shortlist=6

### Shortlist highlights
- SMACS-J0723.3-7327 source 1063 at (x=846, y=735): F090/F444=0.000, score=0.957, status=keep, channel=dropout_strict, rejections=mid_band_coverage_too_low, required_filters_incomplete, falsification:mid_unmeasured_offchip
- SMACS-J0723.3-7327 source 451 at (x=566, y=988): F090/F444=0.000, score=0.940, status=keep, channel=dropout_strict, rejections=mid_band_coverage_too_low, required_filters_incomplete, falsification:mid_unmeasured_offchip
- SMACS-J0723.3-7327 source 16 at (x=654, y=42): F090/F444=0.000, score=0.939, status=keep, channel=dropout_loose, rejections=mid_band_coverage_too_low, required_filters_incomplete, falsification:mid_unmeasured_offchip
- SMACS-J0723.3-7327 source 15 at (x=486, y=40): F090/F444=0.003, score=0.914, status=keep, channel=dropout_loose, rejections=mid_band_coverage_too_low, required_filters_incomplete, falsification:mid_unmeasured_offchip
- SMACS-J0723.3-7327 source 143 at (x=92, y=349): F090/F444=0.000, score=0.891, status=keep, channel=morphology_extended_red, rejections=dropout_not_stable_across_apertures, mid_band_coverage_too_low, required_filters_incomplete, falsification:mid_unmeasured_offchip

### Notable anomalies
- jwst_GS-MEDIUM-HST_F150W_jw01180026001_05201_00002_nrca2_cal (GS-MEDIUM-HST F150W): heavy_tail / potential cosmic ray
- jwst_GS-MEDIUM-HST_F150W_jw01180026001_05201_00002_nrca2_i2d (GS-MEDIUM-HST F150W): heavy_tail / potential cosmic ray
- jwst_GS-MEDIUM-HST_F150W_jw01180026001_05201_00002_nrca2_o026_crf (GS-MEDIUM-HST F150W): heavy_tail / potential cosmic ray
- jwst_GS-MEDIUM-HST_F410M_jw01180026001_17201_00003_nrcalong_cal (GS-MEDIUM-HST F410M): heavy_tail / potential cosmic ray
- jwst_CEERS-NIRSPEC-P5-MR-MSATA_F356W_jw01345064001_03201_00001_nrcalong_cal (CEERS-NIRSPEC-P5-MR-MSATA F356W): heavy_tail / potential cosmic ray

## Rerun instructions
- Ensure API is running: `python run_api.py`
- Rebuild Universe Table: `python discovery/build_universe_table.py`
- Review shortlist: `research_output/highz_shortlist.json`
- View strict-ready datasets: `curl "http://localhost:8000/datasets/?limit=20&strict_ready=true"`
