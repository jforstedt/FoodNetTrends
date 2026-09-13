import contextlib
import csv
import hashlib
import importlib.util
import io
import json
import os
import sys
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


L = load('launch_surveillance_refits'); C = load('collect_surveillance_refits')


def write(path, data):
    with path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(data[0])); writer.writeheader(); writer.writerows(data)


def settings(p, g='combined', start=1996, end=2025):
    return dict(pathogen=p, subgroup=g, analysis_start_year=str(start), analysis_end_year=str(end),
        baseline_start='2019', baseline_end='2019', travel='NO,UNKNOWN,YES', cidt='CIDT+,CX+,PARASITIC',
        states='', colorado_coverage='historical', parasite_end_year='2024', serotype_source='auto',
        selected_serotypes='', travel_stratify='false', catchment_config='')


def diagnostic():
    return dict(max_rhat='1.001', min_ess='5000', n_divergent='0', converged='TRUE', warnings='')


def rate_row(year, count=10, population=100000):
    row = dict(year=str(year), population=str(population), population_check='0', raw_count=str(count),
        raw_check='0', raw_ir=str(count / population * 100000), median=str(count), mean=str(count),
        lower_equitailed=str(count * .5), upper_equitailed=str(count * 1.5),
        lower_hdi=str(count * .4), upper_hdi=str(count * 1.4))
    for field in ('median', 'mean', 'lower_equitailed', 'upper_equitailed', 'lower_hdi', 'upper_hdi'):
        row[field + '_ir'] = str(float(row[field]) / population * 100000)
    return row


def prepared(base, multiple=False):
    source = base / 'source'; source.mkdir()
    selections = [settings('CAMPYLOBACTER')]
    if multiple:
        selections += [settings('SALMONELLA'), settings('STEC', 'nonO157'), settings('YERSINIA'),
                       settings('CRYPTOSPORIDIUM', start=1997, end=2024)]
    for s in selections:
        prefix = s['pathogen'] + '_' + s['subgroup']
        write(source / (prefix + '_analysis_settings.csv'), [s])
        (source / (prefix + '_classification_rules.csv')).write_text('pathogen,rule\n')
    dest = base / 'run space'; command = L.prepare(ROOT, dest, Path('/data'), [source])
    manifest = json.loads((dest / 'manifest.json').read_text())
    for job in manifest['jobs']:
        work = dest / job['task']; output = work / 'spline_results'; prefix = job['prefix']
        s = dict(job['settings'], analysis_start_year=str(job['first_year']), analysis_end_year=str(job['last_year']))
        years = range(job['first_year'], job['last_year'] + 1)
        # Two complete sites make a missing-site failure distinguishable from a missing year.
        model = [dict(year=y, state=state, count=10, population=100000) for y in years for state in ('CA', 'MN')]
        sites = [dict(rate_row(r['year']), state=r['state']) for r in model]
        catches = [rate_row(y, count=20, population=200000) for y in years]
        comparison = [dict(row, baseline_start='2019', baseline_end='2019', baseline_raw_ir='10', baseline_median_ir='10',
            baseline_lower_hdi_ir='4', baseline_upper_hdi_ir='14', relative_risk_lower_hdi='.8', relative_risk_upper_hdi='1.2',
            relative_risk_est='1', percent_change_lower_hdi='-20', percent_change_upper_hdi='20', percent_change_est='0',
            comparison_period='2019-2019') for row in catches]
        write(output / (prefix + '_IRCatch.csv'), catches)
        write(output / (prefix + '_IRSite.csv'), sites)
        write(output / (prefix + '_EstIRRCatch_2019_2019.csv'), comparison)
        write(output / (prefix + '_analysis_settings.csv'), [s])
        write(output / (prefix + '_convergence_diagnostics.csv'), [diagnostic()])
        # Python consumes an independently produced R proof; it does not pretend to deserialize RDS.
        fit = output / (prefix + '_brm.Rds'); fit.write_bytes(b'synthetic checkpoint representation')
        proof = dict(schema_version=1, status='PASS', eligibility_status='PASS',
            fit_sha256=hashlib.sha256(fit.read_bytes()).hexdigest(), model_data=model,
            expected_keys=[dict(year=r['year'], state=r['state']) for r in model],
            diagnostics=dict(diagnostic(), min_ess_bulk=5000, min_ess_tail=5000, n_treedepth_hits=0,
                min_ebfmi=.8, chains=6, post_warmup_draws_per_chain=5001))
        (work / 'saved_fit_validation.json').write_text(json.dumps(proof))
        (work / 'exit_status.txt').write_text('0\n')
    return dest, manifest, command


def collect(dest, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return C.collect(dest, **kwargs)


class RefitTests(unittest.TestCase):
    def test_selective_parallel_and_consistent_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            dest, manifest, command = prepared(Path(temp), multiple=True)
            self.assertEqual(command[command.index('-t') + 1], '1-3'); self.assertNotIn('-tc', command)
            self.assertEqual(len(manifest['jobs']), 3)
            auditor = dest / 'scripts/audit_saved_state_fit.R'
            self.assertEqual(auditor.read_bytes(), (ROOT / 'scripts/audit_saved_state_fit.R').read_bytes())
            self.assertEqual(manifest['source_sha256']['audit_saved_state_fit.R'], hashlib.sha256(auditor.read_bytes()).hexdigest())
            for job in manifest['jobs']:
                args = job['command']; self.assertIn('--env', args)
                self.assertEqual(args[args.index('--env') + 1], 'OPENBLAS_NUM_THREADS=2,OMP_NUM_THREADS=2,MKL_NUM_THREADS=2')
            for path in dest.rglob('*.sh'): subprocess.check_call(['bash', '-n', str(path)])
            self.assertEqual(collect(dest), 0)
            with tarfile.open(str(dest) + '.tar.gz') as archive:
                self.assertFalse(any(n.lower().endswith('.rds') for n in archive.getnames()))

    def test_worker_audits_successful_fit_and_preserves_fit_status(self):
        for fit_status, audit_status in ((0, 0), (7, 0), (0, 9)):
            with self.subTest(fit_status=fit_status, audit_status=audit_status), tempfile.TemporaryDirectory() as temp:
                base = Path(temp); dest, manifest, _ = prepared(base); job = manifest['jobs'][0]
                work = dest / job['task']; fake = base / 'fakebin'; fake.mkdir(); runtime = fake / 'singularity'
                runtime.write_text('#!' + sys.executable + '\n' +
                    'import json,os,pathlib,sys\n' +
                    'audit=any(x.endswith("audit_saved_state_fit.R") for x in sys.argv)\n' +
                    'with open(os.environ["CALLS"],"a") as h:h.write(("audit" if audit else "fit")+"\\n")\n' +
                    'status=int(os.environ["AUDIT_STATUS" if audit else "FIT_STATUS"])\n' +
                    'if audit:pathlib.Path(sys.argv[-1]).write_text(json.dumps({"status":"PASS" if status==0 else "REVIEW_REQUIRED"}))\n' +
                    'print("synthetic audit" if audit else "synthetic fit")\n' +
                    'sys.exit(status)\n')
                runtime.chmod(0o755)
                calls = base / 'calls.txt'
                env = dict(os.environ, PATH=str(fake) + ':' + os.environ['PATH'], CALLS=str(calls),
                           FIT_STATUS=str(fit_status), AUDIT_STATUS=str(audit_status))
                result = subprocess.run(['bash', str(work / 'run.sh')], env=env,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                self.assertEqual(result.returncode, fit_status, result.stderr)
                self.assertEqual((work / 'exit_status.txt').read_text().strip(), str(fit_status))
                if fit_status:
                    self.assertEqual(calls.read_text().splitlines(), ['fit'])
                    self.assertEqual((work / 'audit_exit_status.txt').read_text().strip(), 'NOT_RUN_FIT_FAILED')
                else:
                    self.assertEqual(calls.read_text().splitlines(), ['fit', 'audit'])
                    self.assertEqual((work / 'audit_exit_status.txt').read_text().strip(), str(audit_status))
                    self.assertIn('synthetic audit', (work / 'audit.log').read_text())
                    self.assertEqual(json.loads((work / 'saved_fit_validation.json').read_text())['status'],
                                     'PASS' if audit_status == 0 else 'REVIEW_REQUIRED')
                self.assertIn('synthetic fit', (work / 'fit.log').read_text())

    def test_rejects_malformed_or_incomplete_outputs(self):
        variants = ('nan', 'infinity', 'negative_count', 'zero_population', 'reverse_interval', 'duplicate',
                    'missing_site', 'missing_column', 'fractional_year', 'wrong_rate', 'wrong_baseline', 'wrong_total')
        for variant in variants:
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp:
                dest, manifest, _ = prepared(Path(temp)); job = manifest['jobs'][0]
                path = dest / job['task'] / 'spline_results' / (job['prefix'] + '_IRSite.csv')
                data = C.rows(path)
                if variant == 'nan': data[0]['mean'] = 'NaN'
                elif variant == 'infinity': data[0]['upper_hdi'] = 'Inf'
                elif variant == 'negative_count': data[0]['raw_count'] = '-1'
                elif variant == 'zero_population': data[0]['population'] = '0'
                elif variant == 'reverse_interval': data[0]['lower_hdi'] = '100'
                elif variant == 'duplicate': data.append(dict(data[0]))
                elif variant == 'missing_site': data = [r for r in data if r['state'] != 'MN']
                elif variant == 'missing_column':
                    for row in data: row.pop('mean_ir')
                elif variant == 'fractional_year': data[0]['year'] = '1996.5'
                elif variant == 'wrong_rate': data[0]['mean_ir'] = '100'
                elif variant == 'wrong_total':
                    data[0]['raw_count'] = '11'; data[0]['raw_ir'] = '11'
                elif variant == 'wrong_baseline':
                    path = path.with_name(job['prefix'] + '_EstIRRCatch_2019_2019.csv')
                    data = C.rows(path); data[0]['baseline_start'] = '2018'
                write(path, data)
                self.assertEqual(collect(dest), 1)

    def test_saved_fit_proof_is_mandatory_and_bound_to_model(self):
        variants = ('missing', 'failed', 'bad_hash', 'omitted_model_site', 'duplicate_expected_key',
                    'failed_eligibility', 'bad_diagnostics', 'checkpoint_changed', 'treedepth', 'ebfmi', 'tail_ess')
        for variant in variants:
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp:
                dest, manifest, _ = prepared(Path(temp)); job = manifest['jobs'][0]; work = dest / job['task']
                path = work / 'saved_fit_validation.json'; proof = json.loads(path.read_text())
                if variant == 'missing': path.unlink()
                elif variant == 'checkpoint_changed':
                    (work / 'spline_results' / (job['prefix'] + '_brm.Rds')).write_text('changed')
                else:
                    if variant == 'failed': proof['status'] = 'REVIEW_REQUIRED'
                    elif variant == 'bad_hash': proof['fit_sha256'] = 'wrong'
                    elif variant == 'omitted_model_site': proof['model_data'] = [r for r in proof['model_data'] if r['state'] == 'CA']
                    elif variant == 'duplicate_expected_key': proof['expected_keys'].append(proof['expected_keys'][0])
                    elif variant == 'failed_eligibility': proof['eligibility_status'] = 'REVIEW_REQUIRED'
                    elif variant == 'bad_diagnostics': proof['diagnostics']['min_ess'] = 'NaN'
                    elif variant == 'treedepth': proof['diagnostics']['n_treedepth_hits'] = 1
                    elif variant == 'ebfmi': proof['diagnostics']['min_ebfmi'] = .1
                    elif variant == 'tail_ess': proof['diagnostics']['min_ess_tail'] = 10
                    path.write_text(json.dumps(proof))
                self.assertEqual(collect(dest), 1)

    def test_legacy_unavailable_population_sd_is_not_an_estimate_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            dest, manifest, _ = prepared(Path(temp)); job = manifest['jobs'][0]
            output = dest / job['task'] / 'spline_results'
            for suffix in ('_IRCatch.csv', '_IRSite.csv', '_EstIRRCatch_2019_2019.csv'):
                path = output / (job['prefix'] + suffix); data = C.rows(path)
                for row in data: row['population_check'] = 'NA'
                write(path, data)
            self.assertEqual(collect(dest), 0)
            path = output / (job['prefix'] + '_IRSite.csv'); data = C.rows(path)
            data[0]['population'] = 'NA'; write(path, data)
            self.assertEqual(collect(dest), 1)

    def test_diagnostic_warnings_are_not_a_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            dest, manifest, _ = prepared(Path(temp)); job = manifest['jobs'][0]
            path = dest / job['task'] / 'spline_results' / (job['prefix'] + '_convergence_diagnostics.csv')
            write(path, [dict(diagnostic(), warnings='Diagnostic extraction warning')])
            self.assertEqual(collect(dest), 1)

    def test_external_recheck_preserves_original_run(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); dest, manifest, _ = prepared(base)
            proofs = base / 'proofs'
            for job in manifest['jobs']:
                work = dest / job['task']; target = proofs / job['task']; target.mkdir(parents=True)
                (target / 'saved_fit_validation.json').write_bytes((work / 'saved_fit_validation.json').read_bytes())
                (work / 'saved_fit_validation.json').unlink()
            before = {str(p.relative_to(dest)): p.read_bytes() for p in dest.rglob('*') if p.is_file()}
            report = base / 'recheck'
            self.assertEqual(collect(dest, validation_dir=proofs, report_dir=report), 0)
            self.assertEqual(before, {str(p.relative_to(dest)): p.read_bytes() for p in dest.rglob('*') if p.is_file()})
            self.assertTrue((report / 'review_summary.json').is_file())
            with tarfile.open(str(report) + '.tar.gz') as archive:
                self.assertFalse(any(n.lower().endswith('.rds') for n in archive.getnames()))
                self.assertTrue(any(n.endswith('saved_fit_validation.json') for n in archive.getnames()))
                self.assertTrue(any(n.endswith('_IRSite.csv') for n in archive.getnames()))
            with self.assertRaisesRegex(ValueError, 'outside'):
                collect(dest, report_dir=dest / 'recheck')

    def test_parent_postrun_directory_can_hold_both_proofs_and_report(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); dest, manifest, _ = prepared(base); report = base / 'postrun'
            for job in manifest['jobs']:
                proof_dir = report / job['task']; proof_dir.mkdir(parents=True)
                (proof_dir / 'saved_fit_validation.json').write_bytes((dest / job['task'] / 'saved_fit_validation.json').read_bytes())
            self.assertEqual(collect(dest, validation_dir=report, report_dir=report), 0)
            with self.assertRaisesRegex(ValueError, 'Existing external'):
                collect(dest, validation_dir=report, report_dir=report)

    def test_unknown_settings_and_baseline_fail_before_plan(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp); s = settings('STEC', 'nonO157'); s['baseline_start'] = '1996'; s['baseline_end'] = '1998'
            write(source / 'STEC_nonO157_analysis_settings.csv', [s])
            with self.assertRaisesRegex(ValueError, 'Baseline'): L.scan([source])
            s = settings('STEC', 'nonO157'); s.pop('travel_stratify'); s.pop('catchment_config')
            write(source / 'STEC_nonO157_analysis_settings.csv', [s]); (source / 'STEC_nonO157_classification_rules.csv').write_text('pathogen,rule\n')
            with self.assertRaisesRegex(ValueError, 'provenance'): L.scan([source])


if __name__ == '__main__': unittest.main()
