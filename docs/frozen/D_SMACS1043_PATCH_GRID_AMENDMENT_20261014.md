# Prospective patch-location injection grid — 2026-10-14

Dated additive amendment to `D_SMACS1043_COMPLETION_20261014.md`, preserving
its original ring grid and every E2 scientific gate. The user also requested
injection recovery at the actual patch location. Historical patch outcomes and
the current same-photon operator replay are already known; this supplemental
grid is not a blind patch test. No injection outcomes have been accessed and
no injection trials have run. Commit this amendment before any future injection.

Fixed patch ICRS center: RA 110.63858928243717 deg,
Dec -73.48487214542632 deg. Use signed fixed-aperture injected fluxes
+1000, +1500 and -1000 nJy. Freeze five east/north angular offsets (arcsec)
relative to that coordinate: (0,0), (+0.05,0), (-0.05,0), (0,+0.05),
(0,-0.05). Construct offsets with spherical sky-coordinate offsets, not a
constant RA increment. One deterministic injection trial per flux/offset in
each of the two original E2 images: 3 × 5 × 2 = 30 supplemental image trials.
The original 1674 ring trials remain required, for 1704 total planned trials.
No outcomes or favorable offsets select this grid.

The same separately identified measured same-field unsaturated point-source
PSF and independently held-out reduced-chi2 ≤2 acceptance remain prerequisites.
They are currently unmet; none of the 30 patch trials is authorized without
them. Record zero executed trials and the blocker until they are met.

Apply every original E2 operator to the same original and injected image copies.
Record incremental recovered flux as injected-image minus original-image flux
at each predetermined coordinate, alongside absolute signed measurements and
centroids. Existing patch flux cannot count as recovery of an added injection.
No data-dependent recentering, offset selection, variance rescaling or
replacement PSF is permitted. Report incremental recovered/input medians and
original detection/centroid outcomes, keeping negative injected sources signed.
An existing positive patch can remain detected after a negative injection;
that fact alone is not a negative-injection false-positive measurement.
The original retained-ring negative-injection null requirement remains binding.

These 30 supplemental scene-response diagnostics do not replace the original
ring completeness/false-positive gates or supply an independent observation.
An injection pass cannot overturn any previous failed null or association gate,
and cannot alone promote or physically reject the source. Original designs
remain untouched. Outputs belong in d_* receipts; list every unrun trial.
