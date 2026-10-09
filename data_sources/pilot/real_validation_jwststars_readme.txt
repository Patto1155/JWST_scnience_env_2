README file for JWSTSTARS - The JWST Resolved Stellar Populations Early Release Science Program
MAST webpage: https://archive.stsci.edu/hlsp/jwststars
Refer to this HLSP with DOI: http://dx.doi.org/10.17909/cn6n-xg90


## Contributor

Danial R. Weisz

## Introduction

The JWST Resolved Stellar Population Early Release Science (ERS) Program obtained NIRCam and NIRISS imaging of 3 resolved stellar targets in the Local Group: globular cluster M92, ultra-faint dwarf galaxy Draco II, and star-forming dwarf galaxy WLM. NIRCam was the primary instrument and observed each target in 4 filters: M92 (F090W, F150W, F277W, F444W), Draco II (F090W, F150W, F360M, F480M), WLM (F090W, F150W, F250M, F430M). NIRISS was used in parallel and obtained imaging in 2 filters (F090W, F150W). The third exposure of M92, for both NIRCam and NIRISS, is not included in the analysis as it suffered from excess astrometric jitter and cannot produce adequate photometry. See Weisz et al. (2024) for more details.

## Data Releases
### Release of photometric catalogs of M92, Draco II, and WLM (V1, Feb. 15 2024)

Using the imaging data described above, the ERS team developed JWST NIRCam and NIRISS modules for DOLPHOT
, a crowded field stellar photometry package widely used in nearby galaxies. This data release includes the full, multiband photometric catalogs produced by DOLPHOT for each field and the id2 drizzled reference images used for astrometrically aligning images for each target. The NIRISS field for Draco II did not contain prominent member stars, and the photometric catalog is not included in this data release.  See the catalog description in the README
file.

The FITS images used for this data release have the following JWST pipeline versioning information: CAL_VER=1.11.4, CRDS_VER=11.17.2, and CRDS_CTX=jwst_p1147.pmap.

### Release of epoch photometric catalog and the RR Lyrae catalogs of WLM (V1, Jul. 17 2026)

The team delivered catalogs of the light curves and pulsation parameters for the RR Lyrae (RRL) stars in WLM that were co-observed with JWST and HST. These catalogs were constructed using Tables 7 and 9 of Slaughter et al. (2026).
 These catalogs can be found under the WLM NIRCam observation on the Portal.

The epoch photometric catalog of the RRLs includes the Modified Julian Date (MJD), the image filter (where 0 corresponds to F090W and 1 corresponds to F150W), and the magnitude and its uncertainty measured by DOLPHOT at each epoch. The RRL star lightcurve parameter catalog includes the best-fit pulsation parameters, including the period, pulsation type, filter-specific amplitudes, filter-specific mean magnitudes, and their associated uncertainties for the WLM RR Lyrae stars co-observed with JWST and HST. It also provides the source IDs, right ascension (RA), declination (Dec), and the chi-square (χ²) metric of the fit.

For a detailed description of the catalogs, please refer to the README
file.
 
## Data Products 

_id2.fits = Drizzled images of the target that was used as a reference image for the DOLPHOT reduction.

_phot.fits = Full-stack 4-band (NIRCAM) photometry or 2-band (NIRISS) tables for each field in the program.

_epoch-phot.fits = Table of epoch photometry and error for each RR Lyrae source identified in WLM

_cat.fits = Tables of the WLM RRL star lightcurve parameters


## CATALOG DESCRIPTION

### Photometric catalog (*_phot.fits)
The photometric catalogs are stored as binary fits tables. The catalogs were constructed as described in Weisz et al. (2024). The photometric reductions were performed using the DOLPHOT (Dolphin 2000, 2016) stellar photometry package using the cal files provided by the JWST pipeline, with pipeline versioning references above and stored in the fits headers.

The columns contained in each fits file are summarized below and are also contained in the headers of each fits file.

We have not applied any culling criteria to these catalogs. Weisz et al. (2024) and Warfield et al. (2023) provide suggestions for culling criteria that are applicable to the short wavelength NIRCam data. However, given the multiband nature of the data and the wide range of possible science use cases, users are encouraged to explore catalog culling criteria tailored to their science case.

    Number - Object number in the catalog 
    RA - ICRS Right Ascension of the source in decimal degrees, aligned to Gaia DR3
    DEC - ICRS Declination of the source in decimal degrees, aligned to Gaia DR3
    X - X value of the pixel position on the reference drizzled image
    Y - Y value of the pixel position on the reference drizzled image
    OBJECT TYPE - Object type (1=bright star, 2=faint, 3=elongated,
        4=hot pixel, 5=extended)

    These are followed by 8 columns for each filter, described in detail in the 
    DOLPHOT documentation (http://americano.dolphinsim.com/dolphot/dolphot.pdf).

    [filter name]_VEGA - magnitude for the source, Vega system
    [filter name]_ERR - uncertainty in magnitude (Poisson noise only)
    [filter name]_CHI - goodness-of-fit to the PSF
    [filter name]_SNR - signal-to-noise ratio of the measurement
    [filter name]_SHARP - sharpness of the source
    [filter name]_ROUND - roundness of the source
    [filter name]_CROWD - crowding of the source (difference that
        subtracting neighbors has on the measured magnitude of the source)
    [filter name]_FLAG - DOLPHOT quality flag

    Null values are indicated by 99.999 in the VEGA columns and 9.999 in the ERR columns.

### Epoch Photometric catalog (*_epoch-phot.fits)
The columns contained in the epoch photometry fits file are summarized below. Each row corresponds to a single observational epoch.

    MJD - The time of each observation
    filtnum - The filter the observation was taken with (where 0 corresponds to F090W and 1 corresponds to F150W)

    These are followed by 2 columns for each RR Lyrae candidate source:

    mag-[source ID] - The brightness of the source in the observation, in magnitudes
    e_mag-[source ID] - The uncertainty on the brightness of the source, in magnitudes, from DOLPHOT


### RRL lightcurve parameter catalog (*_cat.fits)
The RR Lyrae catalogs were constructed as described in Slaughter et al. (2026). The epoch photometry table has columns for the MJD, the filter of the image (where 0 corresponds to F090W and 1 corresponds to F150W), and the magnitude and uncertainty as obtained by Dolphot at that epoch. The columns contained in the catalog fits file are summarized below.

    ID - The Dolphot source ID from the JWST data reduction
    ID-HST - The Dolphot source ID from the co-spatial HST data reduction
    RAdeg - The Right Ascension in degrees
    DEdeg - The Declination in degrees
    Chi2 - The chi squared metric for the best fit pulsation template
    Type - The pulsation type ('ab' for primary-mode or 'c' for first-overtone)
    P - The period of pulsation
    e_P - The lower uncertainty on the period
    E_P - The upper uncertainty on the period
    F090W-Amp - The amplitude in the F090W band
    e_F090W-Amp - The lower uncertainty on the F090W amplitude
    E_F090W-Amp - The upper uncertainty on the F090W amplitude
    F090W-mag - The magnitude in the F090W band
    e_F090W-mag - The lower uncertainty on the F090W magnitude
    E_F090W-mag - The upper uncertainty on the F090W magnitude
    F150W-Amp - The amplitude in the F150W band
    e_F150W-Amp - The lower uncertainty on the F150W amplitude
    E_F150W-Amp - The upper uncertainty on the F150W amplitude
    F150W-mag - The magnitude in the F150W band
    e_F150W-mag - The lower uncertainty on the F150W magnitude
    E_F150W-mag - The upper uncertainty on the F150W magnitude


## Publications

An overview of Resolved Stellar Population ERS program can be found in:
Weisz, D. R., et al., 2023, ApJS, 268, 15

A detailed description of the DOLPHOT NIRCam and NIRISS photometry modules can be found in the following:
Weisz, D. R., et al., 2024, ApJS, 271, 47

The WLM RR Lyrae analysis can be found in:
Slaughter, C. M., et al. 2026, Accepted to ApJ (arXiv:2602.21205)

Other ERS papers that make use of this data include:

Warfield, J. T., et al., 2023, RNASS, 7, 23
McQuinn, K. B. W., et al., 2024, ApJ, 961, 16
Boyer, M. L., et al., 2024, submitted to ApJ 


## REFERENCES

Dolphin, A. E., 2000, PASP, 112, 1383
Dolphin, A. E., 2016, ASCL, 1608.013 

