import csv
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import county_forecast_artifacts as artifacts


def write(path, rows):
    with path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def forecast_fixture(base):
    work = base / 'forecast'; report = work / 'result/reports'; report.mkdir(parents=True)
    audit = base / 'audit'; (audit / 'reports').mkdir(parents=True)
    nodes = artifacts.csvrows(ROOT / 'analysis_configs/county_pilot/counties.csv')
    write(audit / 'reports/graph_nodes.csv', nodes)
    panel = audit / 'county_panel_INTERNAL.rds'; panel.write_bytes(b'synthetic checked input')
    task = dict(id='forecast', kind='forecast', pathogen='SALMONELLA', model='spatial_county_time', origin=2011, horizon=3, train_start=2004, audit=str(audit))
    (report / 'status.txt').write_text('FORECAST_CHECK_COMPLETE\n')
    write(report / 'split.csv', [dict(model=task['model'], train_start=2004, train_end=2011, test_start=2012, test_end=2014,
        evaluation_horizon=3, training_cells=486 * 8, heldout_cells=486 * 3, heldout_counts_masked='TRUE', draws=4000)])
    write(report / 'panel_checksum.csv', [dict(file=str(panel), md5=artifacts.digest(panel, 'md5'))])
    rows = [dict(fips=node['fips'], state=node['state'], year=year, population=10000, observed=0,
        mean_expected=.2, lower95=0, lower50=0, median=0, upper50=1, upper95=2,
        log_predictive_density=math.log(.8), predicted_zero_probability=.8, zero_brier=.04,
        covered95='TRUE', covered50='TRUE', density_relative_mcse=.1, randomized_pit=.2, training_cases_band='01 zero')
        for node in nodes for year in (2012, 2013, 2014)]
    write(audit / 'reports/population_audit.csv', [dict(fips=r['fips'], state=r['state'], year=r['year'], population=10000, population_status='ok') for r in rows])
    for name in ('heldout_cells_INTERNAL.csv', 'historical_reference_cells_INTERNAL.csv'): write(report / name, rows)
    write(report / 'forecast_specification.csv', [dict(version='training_origin_rw1_v1', training_start=2004, training_end=2011,
        prediction_end=2014, training_years=8, domain_years=11, training_precision_scale=1)])
    write(report / 'temporal_constraint.csv', [dict(year=y, centering_weight=.125 if y <= 2011 else 0) for y in range(2004, 2015)])
    cells = {(r['fips'], r['state'], r['year']): r for r in rows}; aggregates = []; scores = []
    for (grouping, group), data in artifacts.forecast_groups(cells).items():
        n = len(data)
        aggregates.append(dict(grouping=grouping, group=group, cells=n, observed_total=0, expected_total=.2*n,
            observed_zeros=n, expected_zeros=.8*n, total_lower95=0, total_median=.2*n, total_upper95=n,
            zero_lower95=0, zero_median=.8*n, zero_upper95=n, zero_upper_tail=.5))
        scores.append(dict(grouping=grouping, group=group, cells=n, sum_log_predictive_density=math.log(.8)*n,
            mean_absolute_error=.2, mean_zero_brier=.04, coverage95=1, coverage50=1, mean_interval95_width=2, max_density_relative_mcse=.1))
    write(report / 'heldout_aggregate_checks_INTERNAL.csv', aggregates); write(report / 'heldout_scores_INTERNAL.csv', scores)
    return work, task


class ArtifactTests(unittest.TestCase):
    def test_consistent_forecast_and_matching_reference(self):
        with tempfile.TemporaryDirectory() as temp:
            work, task = forecast_fixture(Path(temp))
            self.assertEqual(artifacts.validate_task_outputs(work, task)['validated_cells'], 1458)

    def test_rejects_both_models_missing_same_county_and_numeric_errors(self):
        for case in ('both_omit', 'duplicate', 'nan', 'negative_population', 'interval', 'coverage', 'population_mismatch', 'split', 'future_centering', 'aggregate'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                work, task = forecast_fixture(Path(temp)); report = work / 'result/reports'
                path = report / 'heldout_cells_INTERNAL.csv'; rows = artifacts.csvrows(path)
                if case == 'both_omit':
                    target = rows[0]['fips']; rows = [r for r in rows if r['fips'] != target]
                    write(report / 'historical_reference_cells_INTERNAL.csv', rows)
                elif case == 'duplicate': rows.append(dict(rows[0]))
                elif case == 'nan': rows[0]['mean_expected'] = 'NaN'
                elif case == 'negative_population': rows[0]['population'] = '-1'
                elif case == 'interval': rows[0]['lower95'] = '100'
                elif case == 'coverage': rows[0]['covered95'] = 'FALSE'
                elif case == 'population_mismatch': rows[0]['population'] = '9999'
                elif case == 'split':
                    path = report / 'split.csv'; rows = artifacts.csvrows(path); rows[0]['test_end'] = '2019'
                elif case == 'future_centering':
                    path = report / 'temporal_constraint.csv'; rows = artifacts.csvrows(path); rows[-1]['centering_weight'] = '.125'
                elif case == 'aggregate':
                    path = report / 'heldout_scores_INTERNAL.csv'; rows = artifacts.csvrows(path); rows[0]['coverage95'] = '.5'
                write(path, rows)
                with self.assertRaises(ValueError): artifacts.validate_task_outputs(work, task)

    def test_horizon_requires_all_four_successful_checks(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp); report = work / 'result'; report.mkdir()
            (report / 'status.txt').write_text('HORIZON_INVARIANCE_PASS\n')
            checks = [dict(check=name, status='PASS', **{'pass': 'TRUE'}) for name in ('spatial_baseline', 'spatial_county_time', 'iid_baseline', 'iid_county_time')]
            write(report / 'checks.csv', checks)
            self.assertEqual(artifacts.validate_task_outputs(work, dict(kind='horizon'))['validated_checks'], 4)
            write(report / 'checks.csv', checks[:-1])
            with self.assertRaises(ValueError): artifacts.validate_task_outputs(work, dict(kind='horizon'))

    def test_calibration_requires_all_eighteen_metrics(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp); report = work / 'result'; report.mkdir()
            (report / 'status.txt').write_text('TASK_COMPLETE: synthetic fixture\n')
            task = dict(kind='calibration', density='sparse', variant='iid', replicate=1)
            summary = dict(status='TASK_COMPLETE', density='sparse', variant='iid', replicate=1, draws=2000,
                           specification=dict(version='county-forecast-calibration-v1'))
            (report / 'task_summary.json').write_text(json.dumps(summary))
            metrics = [dict(density='sparse', variant='iid', replicate=1, method=m, horizon=h, unit=u, coverage=.95,
                mean_width=1, mean_absolute_error=1, mean_predictive_mcse=.01, draws=2000, observations=12 if u=='cell' else 1)
                for m in ('INLA_GAUSSIAN', 'KNOWN_PARAMETER_ORACLE') for h in (1,2,3) for u in ('cell','total','zero_total')]
            write(report / 'metrics.csv', metrics)
            self.assertEqual(artifacts.validate_task_outputs(work, task)['validated_metrics'], 18)
            write(report / 'metrics.csv', metrics[:-1])
            with self.assertRaises(ValueError): artifacts.validate_task_outputs(work, task)

    def test_scalar_reference_requires_complete_scenarios_and_error_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp); report = work / 'result'; report.mkdir()
            (report / 'status.txt').write_text('SCALAR_REFERENCE_PASS\n')
            (report / 'reference_summary.json').write_text(json.dumps(dict(status='SCALAR_REFERENCE_PASS', probability_error_limit=.05)))
            rows = [dict(scenario=s, draws=4000, max_probability_error=.01, exact_lower=-10, exact_median=-9, exact_upper=-8,
                         sample_lower=-10, sample_median=-9, sample_upper=-8, **{'pass': 'TRUE'}) for s in ('zero','sparse','dense','low_rate')]
            write(report / 'scalar_reference.csv', rows)
            self.assertEqual(artifacts.validate_task_outputs(work, dict(kind='reference'))['validated_scenarios'], 4)
            rows[0]['max_probability_error'] = '.06'; write(report / 'scalar_reference.csv', rows)
            with self.assertRaises(ValueError): artifacts.validate_task_outputs(work, dict(kind='reference'))


if __name__ == '__main__': unittest.main()
