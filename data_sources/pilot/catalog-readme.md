JADES - NIRSpec - Data Release 4
Emission line flux tables
------------------------

RELEASE: v5.1.1
DATE: 1 October 2025


Description:
Table of redshifts and emission line fluxes from JADES NIRSpec observations. 
Further details can be found in the JADES NIRSpec Data Release 4 Paper I (Curtis-Lake et al. 2025) and Paper II
(Scholtz, Carniani et al. 2025).

This table (Combined_DR4_external.fits) contains the following extensions:

##1: Obs_info
##2: PRISM_5pix
##3: PRISM_3pix
##4: R1000_5pix
##5: R1000_3pix

The extensions 2 & 3 reports fluxes of emission lines measured from low-resolution
CLEAR/PRISM observations.

The extensions 4 & 5 reports emission line fluxes measured from medium-resolution (R~1000)
F070LP/G140M, F170LP/G235Mand F290LP/G395M observations.

Both tables also report redshifts (measured from the combined low- and
medium-resolution data), and information about the targeting and observations.
A more detailed description of the columns is given below.
More details can be found in Scholtz et al. 2025

-----------------------
Note on target IDs
NIRSpec_ID values contain duplicates due to the fact that the input photometric
catalog was updated frequently throughout the survey. Different targets may 
share the same NIRSpec_ID, even including in the same observing program (PID).
To match galaxies to their spectra, the recommended procedure is to use both the
NIRSpec_ID and TIER  columns or use the Unique_ID which is unique to each target. 
Repeat observations of the same target may or may not have the same NIRSpec_ID and Unique_ID.
NIRCam_ID values are unique, but not all targets have a NIRCam_ID.
-----------------------


-----------------------
Extension 1: Obs_info

Unique_ID      : Unique ID for each ID/Tier combination (see note on target IDs)
PID            : Program ID of the observations
TIER           : Used to uniquely identify observations (see note on target IDs)
TIER_old       : Old verrsion of TIER used in DR1 and DR3. 
                 Used to uniquely identify observations (see note on target IDs)
NIRSpec_ID     : ID used in the NIRSpec input target selection catalog (see note on target IDs)
NIRCam_ID_DR3  : ID of the closest match within 0.2" in the JADES NIRCam data
                  release catalogue (Robertson et al. 2024). Values of -9999
                  mean that no source exists within 0.2" (due to re-segmentation
                  of the images). Values of -1111 indicate targets outside the
                  NIRCam footprint.
NIRCam_ID_DR5  : ID of the closest match within 0.2" in the JADES NIRCam data
                  release 5 catalogue (Johnson and JADES collaboration at al.) 
ObsDate        : Date of NIRSpec-MSA observations 
RA_TARG        : Right Ascension of target as used for target allocation and
                  pathloss correction
Dec_TARG       : Declination of target as used for target allocation and
                  pathloss correction
x_offset       : Intra-shutter offset of the source in arcseconds, averaged
                      over the multiple pointings
y_offset       : Intra-shutter offset of the source in arcseconds, averaged
                      over the multiple pointings
Field          : A string denoting the target field.
GSa            : Selection method used for GOODS-S field
GSb            : Selection method used for GOODS-S field
PC_empt        : Priority class within empt software
Priority       : Priority class in target assignment process
oddball_source : Source catalogue used for oddballs
PC_eMPT_pre_oddball : Priority class within empt software before it was selected
                      as oddball
priority_pre_oddball: Priority class in target assignment process before it was 
                    selected as oddball
F444W_gold_DR3 : Gold sample based on F444W from DR3 photometry
UV_gold_DR3    : Gold sample based on UV magnitude from DR3 photometry
F444W_gold_DR5_beta: Gold sample based on F444W from DR5 beta photometry
UV_gold_DR5_beta:  Gold sample based on UV magnitude from DR5 beta photometry
assigned_Prism     : True if source observed with CLEAR/PRISM, False otherwise
assigned_G140M     : True if source observed with F070LP/G140M, False otherwise
assigned_G235M     : True if source observed with F170LP/G235M, False otherwise
assigned_G395M     : True if source observed with F290LP/G395M, False otherwise
assigned_G395H     : True if source observed with F290LP/G395H, False otherwise
nDither_Pr         : Number of dithers in CLEAR/PRISM
nDither_Gr         : Number of dithers in gratings
nInt_Prism         : Number of integrations (nods and dithers) for the CLEAR/PRISM
                      observations.
nInt_G140M         : Number of integrations (nods and dithers) for the F070LP/G140M
                      observations.
nInt_G235M         : Number of integrations (nods and dithers) for the F170LP/G235M
                      observations.
nInt_G395M         : Number of integrations (nods and dithers) for the F290LP/G395M
                      observations.
nInt_G395H         : Number of integrations (nods and dithers) for the F290LP/G395H
                      observations.
tExp_Prism         : Total exposure time for the CLEAR/PRISM observations [s]
tExp_G140M         : Total exposure time for the F070LP/G140M observations [s]
tExp_G235M         : Total exposure time for the F170LP/G235M observations [s]
tExp_G395M         : Total exposure time for the F290LP/G395M observations [s]
tExp_G395H         : Total exposure time for the F290LP/G395H observations [s]
z_Spec         : Best spectroscopic redshift derived from NIRSpec observations
z_Spec_flag    : Redshift quality flag:
                      A - highly robust, S/N>5 emission lines in R~1000 data
                      B - highly robust, S/N>5 emission lines in Prism/Clear
                      C - secure, visually identified from spectral breaks
                                    and/or low S/N emission lines
                      D - tentative redshifts
                      E - no redshift
z_R1000        : Redshift determined from R1000 observations
z_R1000n       : Number of emission lines in R1000 used to derive the redshift
z_PRISM        : Redshift from PRISM observations [mag] 
MUV            : Absolute UV magnitude measured from PRISM
MUV_u          : upper error on Absolute UV [mag]
MUV_l          : lower error on Absolute UV [mag]


-----------------------
Extensions 2 & 3: CLEAR/PRISM from 3 and 5 pixel extractions

-----------------------
Description of columns:
-----------------------

Unique_ID      : Unique ID for each ID/Tier combination (see note on target IDs)
PID            : Program ID of the observations
TIER           : Used to uniquely identify observations (see note on target IDs)
TIER_old       : Old verrsion of TIER used in DR1 and DR3. Used to uniquely identify observations (see note on target IDs)
NIRSpec_ID     : ID used in the NIRSpec input target selection catalog (see note on target IDs)
NIRCam_ID      : ID of the closest match within 0.2" in the JADES NIRCam data
                  release catalogue (Robertson et al. 2024). Values of -9999
                  mean that no source exists within 0.2" (due to re-segmentation
                  of the images). Values of -1111 indicate targets outside the
                  NIRCam footprint.

z_PRISM        : PRISM redshift 
[LineID]_flux      : Measured emission line flux from the Prism/Clear spectrum
                      in units of x10^-20 erg s-1 cm-2
                      (See list of emission lines below)
[LineID]_err       : Uncertainty on measured emission lines flux
Blnd_[LineIDs]_flux : Total fluxes measured for blended complexes
Blnd_[LineIDs]_err  : Uncertainty on total flux measured for blended complexes

----------------------------------------------------------------------
Disambiguation of emission line and blend labels in Prism/Clear table:
----------------------------------------------------------------------
C4_1549          : CIV 1548,1551
Blnd_He2_O3_1650 : Blend of HeII 1640 + OIII]1660,1666
C3_1907          : CIII] 1907,1909
Mg2_2796         : MgII 2795,2803
O2_3727          : [OII] 3726,3729
Ne3_3869         : [NeIII] 3869
Ne3_3968         : [NeIII] 3968
HD_4102          : H-delta
HG_4340          : H-gamma, where this is not blended with [OIII] 4363
O3_4363          : [OIII] 4363, where this is not blended with H-gamma
Blnd_HG_O3       : Blend of H-gamma + [OIII] 4363
HB_4861          : H-beta, where this is not blended with [OIII] 4959
O3_4959          : [OIII] 4959, where this is not blended with [OIII] 5007
O3_5007          : [OIII] 5007, where this is not blended with [OIII] 4959
Blnd_HB_O3_5007d : Blend of H-beta + [OIII] 4959 + [OIII] 5007
O3_5007d         : Blend of [OIII] 4959 + 5007, where not blended with H-beta
He1_5875         : HeI 5875
O1_6300          : [OI] 6300
HA_6563          : Single component which is a blend of H-alpha and [NII] 6584
S2_6733d         : Blend of [SII] 6718 + 6733, where not blended with H-alpha
Blnd_HA_N2_S2    : Blend of H-alpha + [NII] 6584 + [SII] 6718 + 6733
He1_7065         : HeI 7065
S3_9069          : [SIII] 9069
S3_9532          : [SIII] 9532
PaD_10049        : Pa-delta
He1_10829        : HeI 10829
PaG_10938        : Pa-gamma
PaB_12818        : Pa-beta
PaA_18751        : Pa-alpha

General words on using reported Prism emission line fluxes:
 - Which lines are blended changes as a function of redshift. For example,
   above z>5.3, H-beta, [OIII]4959, [OIII]5007 are well separated and reported
   independently. Between 2<z<5.3 H-beta is reported separately, but
   [OIII]4959+5007 is reported as a blend ("O3_5007d"). Below z<2, the entire
   complex is reported as a blend ("Blnd_HB_O3_5007d")
 - There will be cases where reported lines fluxes contain contributions from
   blending with other faint lines, not explicitly listed here.
   For example, [NeIII]3869 can be blended with HeI 3889 emission.
   The reported flux in such cases reflects the whole complex.


-----------------------
Extensions 4 & 5: R~1000 gratings from 3 and 5 pixels spectra.


-----------------------
Description of columns:
-----------------------

Unique_ID      : Unique ID for each ID/Tier combination (see note on target IDs)
PID            : Program ID of the observations
TIER           : Used to uniquely identify observations (see note on target IDs)
TIER_old       : Old verrsion of TIER used in DR1 and DR3. Used to uniquely identify observations (see note on target IDs)
NIRSpec_ID     : ID used in the NIRSpec input target selection catalog (see note on target IDs)
NIRCam_ID      : ID of the closest match within 0.2" in the JADES NIRCam data
                  release catalogue (Robertson et al. 2024). Values of -9999
                  mean that no source exists within 0.2" (due to re-segmentation
                  of the images). Values of -1111 indicate targets outside the
                  NIRCam footprint.

z_R1000        : Redshift derived from S/N>5 emission lines in the
                  R~1000 grating spectra of this object (if applicable).
z_R1000        : number of detected emission lines used to derived the R1000 redshift 
[LineID]_flux  : Measured emission line flux from the R~1000 spectra in units
                  of x10^-20 erg s-1 cm-2. (See list of emission lines below)
[LineID]_err   : Uncertainty on measured emission lines flux
[LineID]_SNR   : SNR of the emission line measured 
[LineID]_filter: Grating/filter combination used to measure the flux. 


Note: There is typically spectral overlap between the G140M/F070LP and
G235M/F170LP spectra and the G235M/F170LP and G395M/F290LP spectra. In cases
where are prominent emission line falls in an overlapping region (and thus
detected in two independent observations), we une the lowest-resolution observation
(reddest grating) which has generally higher S/N.

-----------------------------------------------------------
Disambiguation of emission line labels in the R~1000 table:
-----------------------------------------------------------
C4_1549   : CIV 1548,1551     *
C3_1907   : CIII] 1907,1909   *
He2_1640  : HeII 1640
O3_1666   : OIII] 1660,1666   *
O2_3727   : [OII] 3726, 3729  *
Ne3_3869  : [NeIII] 3869
Ne3_3968  : [NeIII] 3968
HD_4102   : H-delta
HG_4340   : H-gamma
O3_4363   : [OIII] 4363
HB_4861   : H-beta
O3_4959   : [OIII] 4959
O3_5007   : [OIII] 5007
He1_5875  : HeI 5875
O1_6300   : [OI] 6300
HA_6563   : H-alpha
N2_6584   : [NII] 6584
S2_6718   : [SII] 6718
S2_6733   : [SII] 6733
S3_9069   : [SIII] 9069
S3_9532   : [SIII] 9532
PaD_10049 : Pa-delta
He1_10829 : HeI 10829
PaG_10938 : Pa-gamma
PaB_12818 : Pa-beta
PaA_18751 : Pa-alpha

* These doublets are not resolved into individual components even in these
   R~1000 observations.