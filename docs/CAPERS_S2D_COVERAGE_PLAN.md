# Rectified source-coverage gate

Predeclared before the new download, 2026-10-10. Dependency: exact sourceX1D
and complete source-association inventorya768eb3. That X1D contains no samples
from2.15–3.20um despite MULTIPLE detectors. Question: does the actual public
sourceS2D contain usable rectified pixels there, making the X1D gap an
extraction omission rather than absent supported rectified source coverage?

Predictions: finite wavelength/SCI/positiveERR/nonflagged supported UV pixels
would justify a separate measurement/geometry pilot; zero supported UV pixels
would stop this rectified intermediate route. Unsupported grid pixels are not
zero source flux. If wavelength decoding, source identity or units are
ambiguous, stop and record an accessible geometry dependency.

Budget: one GET of the exact catalog-listed sourceS2D1,353,600bytes, at most
2MiB payload and60seconds acquisition plus60seconds coverage computation.
Prior eight-endpoint companion cap is unchanged; this is a separate pilot.
Verify SHA256, catalog byte identity, sourceID102896/coordinates, association,
calibration/extraction provenance, units and actual wavelength/WCS support.
Count2.15–3.20um pixels before and after finite SCI, positive finite ERR,
DO_NOT_USE/SATURATED and support/weight cuts. Do not fit or extract flux,
interpolate across absent wavelengths or download full CAL/RATE inputs.

This is a calibrated/resampled pipeline product with dependent pixels and
assumed instrument/source response, not raw-pixel reproduction. Independent
actual-input validation must precede any scientific likelihood or stronger
assertion that new observations are required. Stop at zero support, ambiguity
or failed identity and rank lower-stage geometry follow-up if needed.
