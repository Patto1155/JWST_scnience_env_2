# CAPERS companion-detector source-coverage gate

Predeclared 2026-10-10 before additional archive requests. Dependencies:
compact auditba99a31, PIXTAB coverage6ce04a5 and independent review47712c5.

Question: does a public CAPERS NRS1 companion supply usable UV coverage of the
actual source102896 near MoM, despite the author NRS2-only coadd/PIXTAB?
Competing outcomes: a source-specific public X1D containing usable2.15–3.20um
samples may support an independently validated measurement alternative; a
source-specific spectrum with no such samples may resolve this compact archive
route. NRS1 field products alone do not prove source-level UV applicability.

Complete the exact source-association product query for MAST obsid266381037:
reuse its hash-verified page1 (100 of630 records), fetch pages2–7, validate
page/total/parent identities and deduplicate products. Check author SLITS and
detector fields. Select a compact PUBLIC source-specific X1D only if the
filename/source association is exact and catalog size≤1MiB, then verify FITS
source ID, coordinates, calibration provenance, detector/association metadata,
units and actual wavelength/noise/DQ coverage. Never infer identity solely from
field coverage or filenames, or infer zero flux from absent samples.

Budget: at most8 new endpoints,2MiB aggregate accepted metadata+small FITS,
five minutes. One source X1D may be≤1MiB; no full CAL/RATE, guessed-URL search,
flux fitting or acquisition outside these criteria. Stop at completed inventory
and coverage gate, explicit identity failure, inaccessible result or budget.
If the exact compact X1D is oversized, record an accessible size-excluded
dependency rather than declaring new observing time necessary. Independent
actual-input validation is required before any subsequent scientific likelihood.
