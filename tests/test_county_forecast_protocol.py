"""Local eligibility/matrix tests; no R execution or scheduler access."""
import csv
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('protocol', ROOT / 'scripts/county_forecast_protocol.py')
protocol = importlib.util.module_from_spec(spec); spec.loader.exec_module(protocol)


def write(path, data):
    with path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(data[0])); writer.writeheader(); writer.writerows(data)


def fixture(base, pathogen='SALMONELLA'):
    audit = base / pathogen; reports = audit / 'reports'; reports.mkdir(parents=True)
    recon = base / 'reconciliation'; recon.mkdir()
    raw = base / 'raw.sas7bdat'; raw.write_bytes(b'synthetic raw input')
    clean = base / 'clean.csv'; clean.write_bytes(b'synthetic clean input')
    census = base / 'census.sas7bdat'; census.write_bytes(b'synthetic population input')
    panel = audit / 'county_panel_INTERNAL.rds'; panel.write_bytes(b'synthetic panel - read independently only by R runtime')
    (reports / 'status.txt').write_text('INPUT_AUDIT_PASS\n')
    (recon / 'status.txt').write_text('RAW_CLEAN_DEFAULT_HYPOTHESIS_MATCH\n')
    write(recon / 'input_checksums.csv', [dict(file=str(p), md5=protocol.checksum(p, 'md5'), unchanged='TRUE') for p in (raw, clean, panel)])
    write(reports / 'input_checksums.csv', [dict(file=str(p), md5=protocol.checksum(p, 'md5')) for p in (clean, census)])
    end = 2017 if pathogen == 'CRYPTOSPORIDIUM' else 2019
    write(reports / 'observation_scope.csv', [dict(pathogen=pathogen, start_year=2004, end_year=end)])
    write(reports / 'case_flow.csv', [dict(stage='%s 2004-%s' % (pathogen, end), records=100)])
    nodes = protocol.rows(ROOT / 'analysis_configs/county_pilot/counties.csv')
    write(reports / 'graph_nodes.csv', nodes)
    shutil.copyfile(str(ROOT / 'analysis_configs/county_pilot/edges.csv'), str(reports / 'graph_edges.csv'))
    write(reports / 'population_audit.csv', [dict(fips=n['fips'], state=n['state'], year=y, population=10000, population_status='ok')
                                          for n in nodes for y in range(2004, end + 1)])
    write(reports / 'state_year_reconciliation.csv', [dict(state='CA', year=2004, selected_cases=0, direct_matched_cases=0)])
    return dict(audit=str(audit), reconciliation=str(recon))


class ProtocolTests(unittest.TestCase):
    def test_predeclared_matrix_and_conditional_hindcast_limits(self):
        plan = protocol.build_protocol(Path('/does/not/exist'), verify_inputs=False)
        self.assertEqual(len(plan['tasks']), 54)
        self.assertEqual(len({t['id'] for t in plan['tasks']}), 54)
        self.assertEqual(plan['maximum_inla_fits'], 54)
        for pathogen in protocol.PATHOGENS:
            tasks = [t for t in plan['tasks'] if t['pathogen'] == pathogen]
            self.assertEqual(len(tasks), 6)
            for task in tasks:
                self.assertEqual(task['test_end'] - task['origin'], 3)
                self.assertGreaterEqual(task['origin'] - task['train_start'] + 1, 8)
                self.assertLessEqual(task['test_end'], 2017 if pathogen == 'CRYPTOSPORIDIUM' else 2019)
                self.assertIn('conditional hindcast', task['population_assumption'])
                self.assertEqual(task['required_gate'], 'CALIBRATION_AND_HORIZON_PASS')
            for origin in {t['origin'] for t in tasks}:
                pair = [t for t in tasks if t['origin'] == origin]
                self.assertEqual({t['model'] for t in pair}, set(protocol.MODELS))
                self.assertEqual(pair[0]['audit'], pair[1]['audit'])
                self.assertEqual(pair[0]['test_end'], pair[1]['test_end'])
        self.assertTrue(all(s['eligibility_status'] == 'UNVERIFIED' for s in plan['sources'].values()))
        self.assertIn('county_pilot_audit_20260912_205807_702050', plan['sources']['SALMONELLA']['audit'])
        self.assertIn('crypto_coverage_correction', plan['sources']['CRYPTOSPORIDIUM']['audit'])

    def test_verified_source_preserves_exact_panel_lineage(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); source = fixture(base)
            plan = protocol.build_protocol(base, ['SALMONELLA'], sources={'SALMONELLA': source})
            self.assertEqual(len(plan['tasks']), 6)
            verified = plan['sources']['SALMONELLA']
            self.assertEqual(verified['eligibility_status'], 'AUDIT_PROVENANCE_VERIFIED')
            self.assertEqual(verified['panel_sha256'], protocol.checksum(Path(source['audit']) / 'county_panel_INTERNAL.rds'))
            self.assertTrue(verified['evidence_sha256'])
            self.assertIn('R validate_panel', verified['runtime_requirement'])

    def test_rejects_stale_or_incomplete_inputs(self):
        for case in ('raw_changed', 'panel_changed', 'wrong_panel_path', 'failed_audit', 'failed_reconciliation',
                     'missing_population_cell', 'duplicate_population_cell', 'invalid_population', 'wrong_pathogen'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                base = Path(temp); source = fixture(base); reports = Path(source['audit']) / 'reports'
                if case == 'raw_changed': (base / 'raw.sas7bdat').write_text('changed')
                elif case == 'panel_changed': (Path(source['audit']) / 'county_panel_INTERNAL.rds').write_text('changed')
                elif case == 'wrong_panel_path':
                    path = Path(source['reconciliation']) / 'input_checksums.csv'; data = protocol.rows(path)
                    data[-1]['file'] = str(base / 'different_panel.rds'); write(path, data)
                elif case == 'failed_audit': (reports / 'status.txt').write_text('FAIL')
                elif case == 'failed_reconciliation': (Path(source['reconciliation']) / 'status.txt').write_text('FAIL')
                elif case == 'wrong_pathogen':
                    write(reports / 'observation_scope.csv', [dict(pathogen='LISTERIA', start_year=2004, end_year=2019)])
                else:
                    path = reports / 'population_audit.csv'; data = protocol.rows(path)
                    if case == 'missing_population_cell': data.pop()
                    elif case == 'duplicate_population_cell': data.append(data[0])
                    else: data[0]['population'] = 'NaN'
                    write(path, data)
                with self.assertRaises((ValueError, OSError)):
                    protocol.validate_source('SALMONELLA', source)

    def test_crypto_rejects_old_false_zero_years(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); source = fixture(base, 'CRYPTOSPORIDIUM')
            self.assertEqual(protocol.validate_source('CRYPTOSPORIDIUM', source)['end_year'], 2017)
            path = Path(source['audit']) / 'reports/observation_scope.csv'
            write(path, [dict(pathogen='CRYPTOSPORIDIUM', start_year=2004, end_year=2019)])
            with self.assertRaisesRegex(ValueError, 'observation window'):
                protocol.validate_source('CRYPTOSPORIDIUM', source)

    def test_unknown_duplicate_or_empty_pathogen_selection_is_not_silently_skipped(self):
        for selection in ([], ['SALMONELLA', 'SALMONELLA'], ['UNKNOWN']):
            with self.assertRaises(ValueError): protocol.build_protocol(Path('/unused'), selection, verify_inputs=False)


if __name__ == '__main__': unittest.main()
