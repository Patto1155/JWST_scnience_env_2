# CAPERS pixel-table UV coverage gate

Predeclared 2026-10-10 before the new PIXTAB download. Base: immutable compact
auditba99a31. Question: does its publicly accessible PIXTAB contain usable
2.15–3.20um rows outside the released3.938–5.502um one-dimensional spectrum?

Competing predictions: usable source/profile rows in the UV could justify a
separate consistent measurement pilot; zero UV rows would stop the UV nitrogen
track on this intermediate. Missing coverage is not zero line flux. A PIXTAB
with invalid geometry/contributor/settings identity cannot support a new fit.
Six distinct exposure/nod groups are not automatically independent: the author
signed sky operator can reuse inputs across them. Inspect shared-sky witnesses.

Expected gain: resolve whether a small public intermediate contains information
absent from the released coadd before acquiring any full CAL/RATE products.

Budget: one PIXTAB GET, one HEAD only if needed; at most5MiB total accepted
payload,60seconds acquisition and60seconds analysis. Prior HEAD advertises
4,475,520bytes and ETag3740b9e9ddecfe9a8ef5cd559c56ea3f. Reuse that metadata
unless it fails identity validation. No other downloads or flux fits.

Validation: verify whole-file bytes, SHA256, single-part ETag/MD5, FITS schema,
18 ordered contributor identities, source/settings consistency with the
hash-verified compact spectrum, profile signs, positive pathloss/noise and
finite wavelengths. Count total and usable UV rows per exposure and group;
usable means finite fields, positive variance/pathloss/dwave/exptime, nonzero
profile and the established cross-dispersion extraction range. Distinguish
coverage rows from source identity/line significance or empirical calibration.
Stop after the coverage gate or any failed identity/geometry check. An
independent validator must inspect the input and counts before scientific use.
