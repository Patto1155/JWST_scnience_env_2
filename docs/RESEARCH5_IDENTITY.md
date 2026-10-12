# DDE 54: identity and prior variability

12 October 2026. Independent identity/novelty metadata check, separate from
IR time-series measurements and the unopened SPHEREx outcome. Parent cap:
5,000,000 new response-body bytes. All queries below are free public CDS
catalog cone queries; response text preserves the full request, catalog
identity, coordinate frame, epoch, column definitions and query time.

The source is **DDE 54, an already discovered variable YSO candidate**,
including before Gaia DR3. A new claim may concern its empirically validated temporal pattern;
it cannot concern first identification of this source as young or variable.
No uniquely confirmed physical mechanism or resolved stellar origin follows
from these metadata.

## Exact associations

Input coordinate: RA 57.6419783°, Dec +35.5856917°.

| Primary catalog | Exact matched source | Result |
|---|---|---|
|Current VSX, B/vsx/vsx (version 2026-10-05)|DDE 54, OID 476580, 0.05″ offset|YSO, B range 17.0–20.9; period and epoch blank.|
|Marton et al. 2016, J/MNRAS/458/3479/clasi-ii|AllWISE J035034.07+353508.5, 0.040″ offset|Already selected as a Class I/II YSO candidate; CDS recno 133638 is a row locator, not a physical name.|
|Gaia DR3 I/358/vclassre|219690291611604480, effectively zero offset|YSO is the best variability class; classifier score 0.6442687.|
|Marton et al. 2019, II/360/catalog|Gaia DR2 219690291611604480 → the exact AllWISE designation|Probabilistic classifications disagree with the YSO selection: all bands YSO 0.2974 / extragalactic 0.6884; without W3/W4, YSO 0.0492 / extragalactic 0.9506.|
|AllWISE II/328/allwise|J035034.07+353508.5, 0.040″ offset|W1 11.871±0.024, W2 11.132±0.021, W3 9.332±0.036, W4 7.699±0.137 mag; J/H/K 14.471/13.591/12.854 mag.|

Machine-learning labels are neither spectroscopy nor independent physical
confirmation. The 2019 table contains broad probabilistic classifications,
not only selected YSOs; this source fails the paper's high-confidence YSO
criterion. Its membership in that table alone is not a YSO discovery.

Primary sources: Marton et al. (2016), MNRAS 458, 3479,
https://arxiv.org/abs/1602.05777; Marton et al. (2019), MNRAS 487, 2522,
https://academic.oup.com/mnras/article/487/2/2522/5489195; Gaia DR3 YSO
validation, Marton et al. (2023), A&A 674, A21,
https://arxiv.org/abs/2206.05796. The actual catalog rows, rather than an
absence of web search results, establish the associations above.

## Astrometry and blending limits

Exact Gaia DR3 I/355/gaiadr3 row: parallax 2.4852±0.1514 mas,
formal ratio 16.4189; proper motion +3.373, −4.526 mas/year. Quality:
RUWE 1.005, excess noise 0, excess-noise significance 0, 19 visibility
periods, 405 good along-scan observations and one bad, five-parameter
solution (Solved=31), duplicated_source=0, NSS=0, IPD multi-peak and
odd-window fractions both 0%, IPD goodness-of-fit harmonic amplitude 0.103.
These support a well-fitted finite-parallax optical point source. They do
not independently establish a disk, young age or sole origin of unresolved
mid-IR emission.

Gaia G/BP/RP = 18.097454/19.743052/16.766521 mag; raw BP/RP excess
factor 1.593 at BP−RP 2.976531. This raw color-dependent factor is not a
corrected-excess statistic. The table records two blended BP and one
blended RP transits, zero contaminated transits. Parent's separate
10″ Gaia cone contained no second cataloged source. Catalog isolation
cannot rule out a faint or close unresolved infrared blend.

AllWISE PSF reduced chi-square values are 0.993/1.010 in W1/W2,
extension flag 0, nb=1, na=0, photometric quality AAAB, zero W1/W2
saturation fractions. Historical variability flag is 110n. Contamination
flag 0o00 contains a lower-case W2 artifact flag; this must accompany
historical SED or classification claims. These flags do not test the
later unWISE temporal pattern or locate the changing emission within an
unresolved source.

## Negative searches and their scope

No row within 5″ in the queried Auriga-California regional tables
J/ApJ/786/37 (Broekhoven-Fiene et al. 2014) and J/ApJ/764/133
(Harvey et al. 2013). These are catalog-specific nonmatches, not proof
of nonmembership in the cloud or general novelty. Several initial
catalog/table guesses were invalid; they are retained in receipts and
are not counted as successful exclusion searches. The correct 2016
YSO catalog is J/MNRAS/458/3479, not J/ApJS/224/28.

The KYSO catalog J/A+A/674/A21 and DR3-era science alerts I/358/scalerts
return no 5″ row. The latter spans July 2014 to May 2017 only; this does
not exclude later alerts. Gavras et al. (2023) J/A+A/674/A22 contains an
exact Gaia-ID association to the 2019 compiled VSX entry 476580, typed YSO,
with no period fields. This was the decisive route to the established name.
No all-sky completeness claim is made. A previously listed YSO candidate
may still have a new temporal characterization; that novelty must be
compared to primary temporal analyses before promotion.


## Prior optical events: established name and discovery record

The primary VSX page
https://www.aavso.org/vsx/index.php?view=detail.top&oid=476580
identifies DDE 54, discovered by Denis Denisenko and initially submitted on
26 January 2017. It records a roughly four-magnitude optical brightening
in September–October 1988 and irregular roughly 1.5-magnitude variations in
Catalina data from 2005–2013. These pre-existing events must be acknowledged
in any interpretation of later infrared high or low states. The entry has
no period, reference epoch or spectral type. It therefore establishes prior
variability and candidate YSO classification, without establishing the
newly proposed multi-year infrared recurrence.

Published aliases on that primary page include 2MASS J03503406+3535085,
CSS_J035034.1+353508, SDSS J035034.07+353508.5, URAT1 628-050273,
USNO-A2.0 1200-01776173, USNO-B1.0 1255-0058323 and
WISE J035034.07+353508.5. The discoverer's primary catalog is
https://scan.sai.msu.ru/~denis/VarDDE.html (independently checked by the
coordinator); it confirms DDE 54 at the same coordinate, YSO type and
17.0–20.9 optical range, with a blank period. SIMBAD's missing older
aliases were an incomplete catalog-linkage result, not scientific novelty.

This identity review is complete. The source was known as variable before
the current campaign; potential novelty is limited to the new measured
infrared temporal behavior and any independently validated new epoch.
A spectroscopy-confirmed young age, a resolved single infrared source and
a unique variability mechanism remain unestablished. No SPHEREx flux
outcome was opened by this reviewer.
