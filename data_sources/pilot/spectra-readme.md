JADES Data Release 4 - NIRSpec

Date: 01 October 2025

README file for the  JADES Survey
MAST webpage: https://archive.stsci.edu/hlsp/jades
Refer to this HLSP with DOI: http://dx.doi.org/10.17909/8tdj-8n28




### SUMMARY
Here the JADES team releases the reduced 2D and 1D extracted spectra.  To mitigate self-subtraction when performing nodded background subtraction for very extended objects, the team releases the PRISM and GRATINGS with a two-point nodding pattern in addition to the default three-point pattern.  Various 1D boxcar extraction apertures are released, which can be chosen to optimize a source’s signal-to-noise.  In total the team produces 3-nod 5-pixel extraction, 3-nod 3-pixel extraction, 2-nod 5-pixel extraction, and 2-nod 3-pixel extraction. The 1D data also include the 3-node, 5-pixel extraction spectrum obtained from each individual exposure and integration. Flux calibrated 1D and 2D spectra are corrected for slit-losses assuming a point-like morphology for all galaxies. As this assumption might not be adequate for extended sources, the team releases the PRISM data with  the slitlets RA,DEC bounding boxes and 4 NIRCam cutout (5”x5”) images: F090W, F150W, F277W, and F444W


### DATA PRODUCTS
1D spectra are available for each grating/filter combination according to the following convention:
hlsp_jades_jwst_nirspec_<tier>-<NIRSpec ID>_<filter>-<grating>_v1.0_x1d.fits
Where:
<tier> is the name of the TIER field, e.g. “goods-s-mediumjwst”
<NIRSpec> is the  NIRSpec ID number of the target
<filter> and <grating> are the specified observing setup, namely “clear/prism,” “f170lp/g235h,” and “f290lp/g395h
2D spectra follow the same convention, but have the extension “s2d.fits”




Data file types:
x1d.fits        1D extracted spectra
s2d.fits        2D reduced spectra


The 1D PRISM spectra have this structure:
No.    Name      Ver    Type      Cards   Dimensions   Format
  0  PRIMARY                  1 PrimaryHDU      35   ()
  1  EXTRACT5PIX1D            1 BinTableHDU     28   706R x 5C   [D, D, D, D, D]
  2  EXTRACT3PIX1D            1 BinTableHDU     28   706R x 5C   [D, D, D, D, D]
  3  INTERMEDIATE             1 BinTableHDU     52   706R x <N>C   [D, D, ...]
  4  REGION                   1 BinTableHDU     33   #R x 6C   [10A, 4D, 4D, 4D, 4D, I]
  5  F090W                    1 ImageHDU        30   (167, 167)   float32
  6  F150W                    1 ImageHDU        30   (167, 167)   float32
  7  F277W                    1 ImageHDU        30   (167, 167)   float32
  8  F444W                    1 ImageHDU        30   (167, 167)   float32


The 1D GRATING spectra have this structure:
No.    Name      Ver    Type      Cards   Dimensions   Format
  0  PRIMARY           1 PrimaryHDU       35   ()
  1  EXTRACT5PIX1D     1 BinTableHDU     28   1454R x 5C   [D, D, D, D, D]
  2  EXTRACT3PIX1D     1 BinTableHDU     28   1454R x 5C   [D, D, D, D, D]
  3  INTERMEDIATE      1 BinTableHDU    160   1454R x 49C   [D, D,....]
  4  REGION            1 BinTableHDU     33   <N>R x 6C   [10A, 4D, 4D, 4D, 4D, I]


The “EXTRACT<N>PIX1D” corresponds to a spectral extraction aperture equal to <N> pixels. Each of these extensions consists of a table with “WAVELENGTH”, “FLUX,” “FLUX_ERR”, “FLUX_NOD2”, “FLUX_NOD2_ERR” values: wavelengths are in microns, fluxes and errors are in units of erg/s/cm2/Angstrom.  “FLUX” and “FLUX_ERR” are the 1D spectra from the 3-nod pattern.  “FLUX_NOD2” and “FLUX_NOD2_ERR” are the results of the 2-nod pattern.
The extension “INTERMEDIATE” consists of a table with the column “WAVELENGTHS”, and two columns ”FLUX_<id_pointing>_<id_integration>_<id_region>”, ”ERR_<id_pointing>_<id_integration>_<id_region>” for each integration, where: <id_pointing> is the ID of the pointing; <id_integration> is the ID of the integration of each pointing; <id_region> is the ID of the DS9 slitlet region reported in the extension “REGION”
The extension “REGION” includes the slit bounding boxes of the various pointings in DS9 region format and consists in the columns:
-SHAPE reports the Region Description (e.g. Polygon) of each slitlet 
-X includes the bounding boxes x-coordinates in pixel units of each slitlet 
-Y includes the bounding boxes y-coordinates in pixel units of each slitlet 
-RA includes the bounding boxes RA-coordinates in deg units of each slitlet 
-DEC includes the bounding boxes DEC-coordinates in deg units of each slitlet 
-COMPONENT reports the ID region  of each slitlet 


“F090W”, “F150W”, “F200W”, and “F444W” extensions are the NIRCam cutout (5”x5”) in nJy unit. 


The 2D spectra have this structure:
No.    Name      Ver    Type      Cards   Dimensions   Format
  0  PRIMARY                       1 PrimaryHDU      35   ()
  1  FLUX                             1 ImageHDU        22   (706, 27)   float64
  2  FLUX_ERR                      1 ImageHDU        22   (706, 27)   float64
  3  WAVELENGTH                    1 ImageHDU         8   (706,)   float64
  4  FLUX_2NOD                     1 ImageHDU        22   (706, 27)   float64
  5  FLUX_ERR_2NOD            1 ImageHDU        22   (706, 27)   float64


“FLUX” and “FLUX_ERR” are 2D arrays of flux and error with the same units as the corresponding 1D data products. “FLUX_2NOD” and “FLUX_ERR_2NOD” are 2D arrays of flux and error from the 2nod pattern.. “WAVELENGTH” is a 1D array of wavelength in microns.