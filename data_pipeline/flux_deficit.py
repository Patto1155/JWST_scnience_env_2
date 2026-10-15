"""Zero-download paired-log diagnosis and frozen real-background injection control."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.special import ndtr
from scipy.stats import binomtest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research_output/flux_deficit_20261015'
SEED = 20261015


def rows() -> list[dict]:
    result = []
    for name, field in [('b_training', 'GS'), ('b_northern_confirmation', 'GN')]:
        report = json.loads((ROOT / f'research_output/calibrated_20261014/{name}.json').read_text())
        for row in report['results']:
            if 'fit' in row:
                result.append(dict(row, field=field, snr=row['published_flux'] / row['published_error'],
                                   ratio=row['fit']['flux_1e20'] / row['published_flux']))
    return result


def fits(data: list[dict], repetitions: int = 10000) -> dict:
    snr = np.array([r['snr'] for r in data])
    y = np.log([r['ratio'] for r in data])
    ids = sorted({r['unique_id'] for r in data})
    groups = [np.flatnonzero([r['unique_id'] == i for r in data]) for i in ids]
    rng = np.random.default_rng(SEED)
    samples = [np.concatenate([groups[i] for i in rng.integers(len(ids), size=len(ids))])
               for _ in range(repetitions)]
    models = {}
    for power in [1, 2]:
        design = np.column_stack([np.ones(len(y)), snr ** (-power)])
        beta = np.linalg.lstsq(design, y, rcond=None)[0]
        boot = np.array([np.linalg.lstsq(design[ix], y[ix], rcond=None)[0] for ix in samples])
        models[str(power)] = dict(a=float(beta[0]), b=float(beta[1]),
                                 ci95=np.quantile(boot, [.025, .975], axis=0).T.tolist(),
                                 residual_sd=float(np.std(y - design @ beta, ddof=2)))
    cutoff = float(np.median(snr))
    return dict(models=models, n=len(data), objects=len(ids), bootstrap_repetitions=repetitions,
                seed=SEED, snr_split=cutoff,
                low_median=float(np.median(np.exp(y[snr <= cutoff]))),
                high_median=float(np.median(np.exp(y[snr > cutoff]))),
                median=float(np.median(np.exp(y))),
                median_ci95=np.quantile([np.median(np.exp(y[ix])) for ix in samples],
                                        [.025, .975]).tolist(),
                log_sd=float(np.std(y, ddof=1)),
                log_mad=float(np.median(abs(y - np.median(y)))),
                sign_test_p=float(binomtest(int(sum(y < 0)), len(y), .5).pvalue),
                negative=int(sum(y < 0)),
                per_row=[{k: r[k] for k in ['unique_id', 'field', 'line', 'configuration',
                                          'snr', 'ratio']} for r in data])


def freeze() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = fits(rows())
    report['injection_protocol'] = {
        'zero_download_bytes': 0, 'seed': SEED, 'bins_true_snr': [5, 7, 10, 15, 25],
        'trials_per_bin': 200,
        'operator': 'unchanged data_pipeline.calibrated_population.marginal_fit; signed flux',
        'background': 'unmodified real compact FLUX; no added independent noise',
        'window_rule': 'centers every 0.04um from min(w)+0.025 to max(w)-0.025; '
                       'exclude centers within 0.04um of listed observed rest lines; '
                       'require >=20 finite positive-error bins within 0.015um; '
                       'select uniformly over all eligible windows with replacement; no flux cuts',
        'excluded_rest_angstrom': [1215.67, 1549, 1640, 1663, 1909, 2799, 3727, 3869,
                                   3889, 3970, 4102, 4341.68, 4862.68, 4960.3,
                                   5008.24, 5877, 6302, 6549, 6564.6, 6585, 6718, 6733],
        'injected_model': 'bin-integrated Gaussian sigma=1 median pixel; center at nominal '
                          'minus 0.25 pixel (prior center); known integrated flux',
        'true_snr_definition': 'injected flux / fixed-template linear continuum-marginalized '
                               'flux standard error, using local FLUX_ERR; not observed catalogue SNR',
        'primary': 'mean signed recovered/injected by true SNR; bootstrap over background objects',
        'null': 'flat ratio 1; H2 comparator exp(a+b/true_SNR) from frozen power1 fit',
        'decision': 'H2-like only if low-bin (5,7) pooled mean 95% object-bootstrap CI '
                    'excludes 1 below and includes frozen H2 comparator; H1-compatible '
                    'if low-bin CI includes 1 and excludes comparator; otherwise inconclusive. '
                    'Single primary pooled contrast; per-bin CIs descriptive, no multiplicity promotion.',
        'caveat': 'empirically line-free means outside a declared strong-line mask, '
                  'not guaranteed absent unknown emission/absorption; trials share backgrounds. '
                  'Flat injection cannot establish H1 without B/C.'}
    (OUT / 'a_frozen.json').write_text(json.dumps(report, indent=2) + '\n')


def windows(data: list[dict], protocol: dict) -> list[dict]:
    candidates = []
    for row in data:
        with np.load(ROOT / row['compact'], allow_pickle=False) as a:
            w, f, e = [a[k] for k in ['WAVELENGTH', 'FLUX', 'FLUX_ERR']]
        known = np.array(protocol['excluded_rest_angstrom']) * (1 + row['z']) / 10000
        for c in np.arange(float(w.min()) + .025, float(w.max()) - .025, .04):
            mask = (abs(w-c) < .015) & np.isfinite(f+e) & (e > 0)
            if np.min(abs(known-c)) < .04 or sum(mask) < 20:
                continue
            candidates.append(dict(row=row, center=float(c)))
    return candidates


def inject() -> None:
    from data_pipeline.calibrated_population import marginal_fit
    frozen_path = OUT / 'a_frozen.json'
    frozen = json.loads(frozen_path.read_text())
    protocol = frozen['injection_protocol']
    data = rows()
    choices = windows(data, protocol)
    if not choices:
        raise RuntimeError('No windows satisfy frozen definition; do not relax')
    rng = np.random.default_rng(SEED)
    trials = []
    baselines = {}
    start = datetime.now(timezone.utc).isoformat()
    for snr in protocol['bins_true_snr']:
        for _ in range(protocol['trials_per_bin']):
            choice = choices[rng.integers(len(choices))]
            row, center = choice['row'], choice['center']
            with np.load(ROOT / row['compact'], allow_pickle=False) as a:
                table = {k: a[k].copy() for k in ['WAVELENGTH', 'FLUX', 'FLUX_ERR']}
            w, e = table['WAVELENGTH'], table['FLUX_ERR'] / 1e-20
            dw = float(np.median(np.diff(w)))
            profile = (ndtr((w+dw/2-center+.25*dw)/dw)
                       - ndtr((w-dw/2-center+.25*dw)/dw)) / (dw*10000)
            mask = (abs(w-center) < .015) & np.isfinite(table['FLUX']+e) & (e > 0)
            design = np.column_stack([np.ones(sum(mask)), (w[mask]-center)/.015,
                                      profile[mask]]) / e[mask, None]
            err = float(np.sqrt(np.linalg.inv(design.T@design)[2, 2]))
            flux = snr * err
            table['FLUX'] += flux * profile * 1e-20
            baseline_key = (row['compact'], center)
            if baseline_key not in baselines:
                baseline_table = dict(table, FLUX=table['FLUX'] - flux * profile * 1e-20)
                baselines[baseline_key] = marginal_fit(baseline_table, center*10000, 0)['flux_1e20']
            baseline = baselines[baseline_key]
            result = marginal_fit(table, center*10000, 0)
            trials.append(dict(unique_id=row['unique_id'], compact=row['compact'],
                               center=center, true_snr=snr, injected=flux,
                               recovered=result['flux_1e20'], ratio=result['flux_1e20']/flux,
                               baseline=baseline, increment_ratio=(result['flux_1e20']-baseline)/flux))
        print(f'completed {snr}: {len(trials)} trials', flush=True)
    summary = []
    for snr in protocol['bins_true_snr']:
        subset = [t for t in trials if t['true_snr'] == snr]
        summary.append(dict(true_snr=snr, **injection_summary(subset),
                            increment=injection_summary([dict(t, ratio=t['increment_ratio']) for t in subset]),
                            h2_prediction=float(np.exp(frozen['models']['1']['a']
                                                + frozen['models']['1']['b']/snr))))
    pooled = injection_summary([t for t in trials if t['true_snr'] in [5, 7]])
    report = dict(start_utc=start, end_utc=datetime.now(timezone.utc).isoformat(),
                  frozen_sha256=hashlib.sha256(frozen_path.read_bytes()).hexdigest(),
                  operator_sha256=hashlib.sha256((ROOT / 'data_pipeline/calibrated_population.py')
                                                .read_bytes()).hexdigest(),
                  access_note='Baseline and injection outcomes first accessed after a_injection_amendment.json commit',
                  eligible_windows=len(choices), eligible_objects=len({c['row']['unique_id']
                                                                    for c in choices}),
                  bytes_downloaded=0, summary=summary, low_pooled=pooled, trials=trials)
    (OUT / 'a_injections.json').write_text(json.dumps(report, indent=2)+'\n')


def injection_summary(trials: list[dict]) -> dict:
    ids = sorted({t['unique_id'] for t in trials})
    groups = [[t['ratio'] for t in trials if t['unique_id'] == i] for i in ids]
    rng = np.random.default_rng(SEED)
    boot = [np.mean(np.concatenate([groups[i] for i in rng.integers(len(ids), size=len(ids))]))
            for _ in range(10000)]
    values = np.array([t['ratio'] for t in trials])
    return dict(n=len(values), objects=len(ids), mean=float(values.mean()),
                median=float(np.median(values)), sd=float(values.std(ddof=1)),
                mad=float(np.median(abs(values-np.median(values)))),
                mean_ci95=np.quantile(boot, [.025, .975]).tolist())


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['freeze', 'inject'])
    args = p.parse_args()
    freeze() if args.mode == 'freeze' else inject()


if __name__ == '__main__':
    main()
