# NEXUS feasibility and novelty gate

Checked: 2026-10-12T00:57:53Z. Read-only investigation; no main-repository changes. Recommendation: **rank low and pivot**. This investigation establishes data accessibility, not a new astrophysical result.

## Literature and novelty

- Stone et al., *NEXUS: Spectral Variability of Little Red Dots and Blue Active Galactic Nuclei at 2 < z < 6*, arXiv:2608.01647, first public August 3, 2026: https://arxiv.org/abs/2608.01647 ; full paper successfully read via https://arxiv.org/html/2608.01647v1 and https://arxiv.org/pdf/2608.01647 . The study uses six Deep epochs (June 1, 2025–March 28, 2026), 17 LRDs and 14 blue AGNs. Continuum and H-alpha ensemble variability, line ratios, cool-LRD subgroups and the apparent NX7607 variability are already examined. Sections 3.1 and 5.2 explicitly warn that line offsets/profile changes can be reproduced by calibration effects in control galaxies. Repeating these measurements would not satisfy this campaign's novelty requirement.
- Son et al., *Probing the Physical Origin of the Balmer Decrement in the Broad-line Region of Nearby Active Galactic Nuclei via Spectral Variability*, arXiv:2511.07714: https://arxiv.org/abs/2511.07714 . Its primary abstract already describes temporal Balmer decrement versus luminosity and continuum color as a test separating reddening from radiative-transfer/excitation effects. A high-redshift application alone is insufficient justification here.
- Quick Release Notes, latest linked arXiv version v2, May 8, 2026: https://arxiv.org/abs/2603.04586 ; https://arxiv.org/html/2603.04586v2 . The 18 planned epochs and roughly two-month release lag are plans; they do not establish released spectra for every scheduled epoch.

## Exact accessible data

Team entrypoint: https://nexus-jwst.github.io/updates/ . Live directory listings were independently fetched using Python requests:

| URL | Observed contents |
|---|---|
| https://ariel.astro.illinois.edu/nexus/qdr/ | NIRCam and NIRSpec subdirectories |
| https://ariel.astro.illinois.edu/nexus/qdr/nirspec/ | Target catalogs ep01–ep06; ep06 modified August 13, 2026 |
| https://ariel.astro.illinois.edu/nexus/qdr/nirspec/fits/ | Only deep1/, deep2/, deep3/, deep4/, deep5/ listed |
| https://ariel.astro.illinois.edu/nexus/qdr/nirspec/fits/deep1/ | 755 spectrum links, plus five navigation/sorting links |
| https://ariel.astro.illinois.edu/nexus/qdr/nirspec/fits/deep5/ | 902 spectrum links, plus five navigation/sorting links |

This is an audit of the documented processed QDR endpoint, **not an exhaustive MAST/DJA search**. No processed ep07+ independent holdout was demonstrated. The ep06 catalog does not establish access to ep06 processed spectra.

Successfully downloaded and parsed in memory:

https://ariel.astro.illinois.edu/nexus/qdr/nirspec/nexus_msa_deep_ep01_targets.fits

- 86,400 bytes; SHA256 `1265dd1ff83f82c50a4f6b644dc27835c475d03e1143532a5539b3ef1d2d2397`.
- 779 catalog rows; 12 columns, including MSAID, coordinates, priority class, F200W/F444W fluxes/errors and vetted redshift/confidence.
- Exact research-lock interpreter `/tmp/jwst-handover-env/bin/python`; one BLAS thread for FITS parsing. No scientific numerical fit or spectrum measurement was run.

## Budget and stopping decision

Authorized acquisition cap: 20 MB; numerical-computation cap: three minutes. Direct HTTP payload acquisition was approximately **3.6 MB**, including repeat literature HTML reads, a 2,270,358-byte paper PDF, directory listings and the 86,400-byte catalog. Some directory lengths were not logged, so the total is approximate. Browser/search-service retrieval bandwidth is not measured or included. Scientific computation was limited to the catalog schema/readability check and was far below the compute cap. No raw JWST exposures, spectra or full imaging mosaics were downloaded, and no files were written in the repository.

The most plausible narrower question was joint temporal Balmer-decrement/continuum-color behavior: dust extinction predicts linked color and line-ratio changes, whereas excitation/transfer changes can differ. However, the listed spectra reuse the study's existing epochs, the method already has a low-redshift literature prior, and wavelength-dependent slit losses plus low PRISM resolution are unresolved confounders. There is no demonstrated independent discriminator with adequate holdout data. Stop this track rather than force a discovery claim.

Reopen only after a verified additional public epoch outside Stone et al.'s first six, or independently calibrated higher-resolution data, provides enough repeat measurements to test a preregistered mechanism contrast. Require simultaneous calibrated/difference photometry and ordinary emission-line controls to bound chromatic slit-loss and wavelength/LSF systematics before treating an apparent variation as physical.
