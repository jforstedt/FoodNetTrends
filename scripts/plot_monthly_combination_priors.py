#!/usr/bin/env python3
"""Plot data-free prior extrapolation summaries; no model fitting."""
import argparse
import csv
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    with (args.directory / 'prior_extrapolation.csv').open() as handle:
        rows = list(csv.DictReader(handle))
    fig, axes = plt.subplots(2, 2, figsize=(10, 7), sharex=True, sharey=True)
    for ax, cutoff in zip(axes.flat, (2011, 2013, 2014, 2016)):
        for model, color in [('rw1', '#0072B2'), ('ar1', '#D55E00'), ('spline', '#009E73')]:
            selected = sorted((r for r in rows if int(r['cutoff']) == cutoff
                               and r['temporal'] == model and r['seasonal'] == 'TRUE'),
                              key=lambda r: int(r['horizon_month']))
            x = [int(r['horizon_month']) for r in selected]
            lo = [float(r['ratio_p025']) for r in selected]
            hi = [float(r['ratio_p975']) for r in selected]
            ax.plot(x, lo, color=color, label=model.upper())
            ax.plot(x, hi, color=color)
        ax.axhline(1, color='grey', linestyle=':', linewidth=1)
        ax.set_yscale('log')
        ax.set_title('Training through {}'.format(cutoff))
        ax.set_xlabel('Months after training')
        ax.set_ylabel('Rate / final training-month rate')
        ax.grid(alpha=.2)
    axes[0, 0].legend()
    fig.suptitle('Central 95% prior ranges with seasonality\n20,000 draws; no observed case data or fitted models')
    fig.tight_layout(rect=(0, 0, 1, .93))
    for suffix in ('png', 'pdf'):
        fig.savefig(str(args.directory / ('prior_extrapolation.' + suffix)), dpi=180)
    plt.close(fig)


if __name__ == '__main__':
    main()
