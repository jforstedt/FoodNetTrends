#!/usr/bin/env python3
"""Inventory documented development years; no private data reads or fitting.

This records the frozen protocol, not an automated certification of run completion,
reporting completeness, or the existence of an independent holdout.
"""
import argparse
import csv
from pathlib import Path

PATHOGENS = ('SALMONELLA', 'CAMPYLOBACTER', 'CRYPTOSPORIDIUM', 'CYCLOSPORA',
             'LISTERIA', 'SHIGELLA', 'STEC', 'VIBRIO', 'YERSINIA')
CANDIDATES = dict(SALMONELLA='AR1_CANDIDATE', CAMPYLOBACTER='RW1_REFERENCE',
                  CRYPTOSPORIDIUM='AR1_CANDIDATE', CYCLOSPORA='UNSUPPORTED',
                  LISTERIA='AR1_CANDIDATE', SHIGELLA='AR1_CANDIDATE',
                  STEC='RW1_REFERENCE', VIBRIO='UNSUPPORTED', YERSINIA='UNSUPPORTED')


def inventory():
    summaries, years = [], []
    for pathogen in PATHOGENS:
        origins = (2011, 2013, 2014) if pathogen == 'CRYPTOSPORIDIUM' else (2011, 2013, 2016)
        end = max(origins) + 3
        evaluation = sorted(set(y for origin in origins for y in range(origin + 1, origin + 4)))
        summaries.append(dict(pathogen=pathogen, training_start=2004,
                              latest_training_end=max(origins), domain_end=end,
                              origins=';'.join(map(str, origins)),
                              evaluated_years=';'.join(map(str, evaluation)),
                              provisional_candidate=CANDIDATES[pathogen],
                              confirmed_independent_period='NONE_ESTABLISHED',
                              evidence='DOCUMENTED_DEVELOPMENT_PROTOCOL',
                              beyond_domain='SURVEILLANCE_CUTOFF' if end == 2017 else 'METADATA_AND_PRIOR_ACCESS_REVIEW_REQUIRED'))
        for year in range(2004, 2026):
            training = [o for o in origins if year <= o]
            evaluated = [o for o in origins if o < year <= o + 3]
            if year <= end:
                status = 'DEVELOPMENT_EXPOSED'
            elif pathogen == 'CRYPTOSPORIDIUM':
                status = 'OUTSIDE_CONFIRMED_SURVEILLANCE'
            elif pathogen == 'CAMPYLOBACTER' and year >= 2024:
                status = 'DIAGNOSTIC_REPORTING_BREAK'
            elif year >= 2025 and pathogen not in ('SALMONELLA', 'STEC'):
                status = 'REPORTING_COMPLETENESS_UNESTABLISHED'
            else:
                status = 'UNASSESSED_EXTENSION_NOT_CONFIRMED_HOLDOUT'
            years.append(dict(pathogen=pathogen, year=year,
                              training_origins=';'.join(map(str, training)),
                              evaluation_origins=';'.join(map(str, evaluated)),
                              period_status=status, independent_holdout_certified=False))
    return summaries, years


def write_inventory(dest):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=False)
    for name, rows in zip(('pathogen_inventory.csv', 'year_inventory.csv'), inventory()):
        with (dest / name).open('w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    return dest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('outdir', help='New directory; existing directories are refused')
    args = parser.parse_args()
    print(write_inventory(args.outdir))
