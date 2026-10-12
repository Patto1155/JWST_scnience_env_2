import json, warnings, time
from pathlib import Path
import numpy as np
from astropy.io import fits
from astropy.coordinates import SkyCoord
import astropy.units as u
warnings.filterwarnings('ignore', category=fits.verify.VerifyWarning)
p=Path('/tmp/jades-dr4-pilot'); t0=time.time()
with fits.open(p/'Combined_DR4_external_v1.2.1.fits') as h:
 o=h[1].data; a=h['R1000_5pix'].data; b=h['R1000_3pix'].data
 assert np.array_equal(o['Unique_ID'],a['Unique_ID']) and np.array_equal(o['Unique_ID'],b['Unique_ID'])
 # Outcome selection remains restricted to GOODS-S. GN outcome values unexamined.
 south=o['Field']=='GS'; z=o['z_Spec']; robust=np.isin(o['z_Spec_flag'],['A','B'])
 af=a['HBaA_6563_flux']; bf=a['HBaB_4861_flux']; ae=a['HBaA_6563_flux_err']; be=a['HBaB_4861_flux_err']
 valid=np.isfinite(af)&np.isfinite(bf)&np.isfinite(ae)&np.isfinite(be)&(af>0)&(bf>0)&(ae>0)&(be>0)
 snr=(af/ae>=10)&(bf/be>=10)
 same=a['HBaA_6563_filter']==a['HBaB_4861_filter']
 selected=np.flatnonzero(south&robust&(z>2)&(z<7)&valid&snr&same)
 # Duplicated ID/tier observations of one sky source grouped within 0.2 arcsec. Choose largest min line SNR, without ratio dependence.
 coords=SkyCoord(o['RA_TARG'][selected]*u.deg,o['Dec_TARG'][selected]*u.deg)
 score=np.minimum(af[selected]/ae[selected],bf[selected]/be[selected]); keep=[]; seen=set()
 for k in np.argsort(-score):
  if int(k) in seen:continue
  sep=coords[k].separation(coords).arcsec
  seen.update(np.flatnonzero(sep<=0.2).tolist());keep.append(int(selected[k]))
 rows=[]
 for i in keep:
  r5=float(af[i]/bf[i]); d5=float((af[i]-2.65*bf[i])/np.hypot(ae[i],2.65*be[i]))
  ba=b['HBaA_6563_flux'][i];bb=b['HBaB_4861_flux'][i]; ea=b['HBaA_6563_flux_err'][i];eb=b['HBaB_4861_flux_err'][i]
  r3=float(ba/bb) if ba>0 and bb>0 and np.isfinite(ba+bb) else None
  d3=float((ba-2.65*bb)/np.hypot(ea,2.65*eb)) if r3 and ea>0 and eb>0 else None
  rows.append(dict(index=int(i),Unique_ID=str(o['Unique_ID'][i]),NIRSpec_ID=int(o['NIRSpec_ID'][i]),TIER=str(o['TIER'][i]),z=float(z[i]),RA=float(o['RA_TARG'][i]),Dec=float(o['Dec_TARG'][i]),ratio_5=r5,ratio_3=r3,threshold_residual_diag_5=d5,threshold_residual_diag_3=d3,min_snr_5=float(min(af[i]/ae[i],bf[i]/be[i])),filter=str(a['HBaA_6563_filter'][i]),ha5=float(af[i]),hb5=float(bf[i]),haerr5=float(ae[i]),hberr5=float(be[i])))
 rows.sort(key=lambda x:x['ratio_5'])
 out=dict(scope='catalog triage only; diagonal-error scores are uncalibrated; same photons aperture checks; GN outcome holdout unexamined',selected_observation_rows=len(selected),sky_deduplicated_rows=len(rows),selected_sub_2p65=sum(x['ratio_5']<2.65 for x in rows),sub_2p65_in_both=sum(x['ratio_5']<2.65 and x['ratio_3'] is not None and x['ratio_3']<2.65 for x in rows),diagonal_score_below_minus3=sum(x['threshold_residual_diag_5']< -3 for x in rows),rows=rows,compute_elapsed_s=time.time()-t0)
 (p/'catalog-pilot.json').write_text(json.dumps(out,indent=2,allow_nan=False))
 print(json.dumps({k:v for k,v in out.items() if k!='rows'},indent=2));print(json.dumps(rows[:15],indent=2))
