"""Exercise selective saved-model sampler plans without R, containers or a scheduler."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import launch_surveillance_sampler_refits as launcher
from collect_surveillance_refits import sha256


def fixture(base):
    root = base / 'checkout'; (root / 'scripts').mkdir(parents=True)
    for name in ('refit_surveillance_sampler.R', 'audit_saved_state_fit.R', 'collect_surveillance_refits.py'):
        source = ROOT / 'scripts' / name
        # Preparation never executes this script. A synthetic placeholder permits testing
        # launcher integration while the separately owned R implementation is being written.
        (root / 'scripts' / name).write_bytes(source.read_bytes() if source.exists() else b'# synthetic preparation fixture\n')
    (root / 'foodnet.sif').write_bytes(b'synthetic container bytes')
    source = base / 'completed source'; (source / 'scripts').mkdir(parents=True)
    for name in ('functions.R', 'trendy.R', 'input_validation.R', 'classification.R'):
        shutil.copyfile(str(ROOT / 'bin' / name), str(source / 'scripts' / name))
    audit = base / 'completed audit'; audit.mkdir()
    jobs = []; reviews = []
    for index, (pathogen, passing) in enumerate((('SHIGELLA', False), ('CAMPYLOBACTER', True), ('VIBRIO', False)), 1):
        task = 'task_%02d' % index; prefix = pathogen + '_combined'
        work = source / task; output = work / 'spline_results'; output.mkdir(parents=True)
        (work / 'classification_rules.csv').write_text('pathogen,rule\n')
        (work / 'source_settings.csv').write_text('pathogen,subgroup\n' + pathogen + ',combined\n')
        (work / 'exit_status.txt').write_text('0\n')
        fit = output / (prefix + '_brm.Rds'); fit.write_bytes(('synthetic model ' + pathogen).encode())
        (output / (prefix + '_analysis_settings.csv')).write_text('pathogen,subgroup\n' + pathogen + ',combined\n')
        (output / (prefix + '_population_used.csv')).write_text('year,state,population\n2019,CA,100000\n')
        (output / (prefix + '_classification_rules.csv')).write_text('pathogen,rule\n')
        proofdir = audit / task; proofdir.mkdir()
        proof = dict(schema_version=1, status='PASS' if passing else 'REVIEW_REQUIRED',
            eligibility_status='PASS', issues=[] if passing else ['Divergent transitions present'],
            fit_sha256=sha256(fit), diagnostics=dict(n_divergent=0 if passing else 3))
        (proofdir / 'saved_fit_validation.json').write_text(json.dumps(proof))
        job = dict(task=task, prefix=prefix, first_year=1996, last_year=2024, source='/previous/outputs',
            settings=dict(pathogen=pathogen, subgroup='combined', states='', baseline_start='2016', baseline_end='2018'),
            command=['singularity', 'exec', 'original.sif', 'Rscript', 'trendy.R', '--cleanFile', '/original/clean.csv'])
        jobs.append(job)
        reviews.append(dict(task=task, analysis=prefix, status='CHECKS_PASS' if passing else 'REVIEW_REQUIRED',
                            issues=[] if passing else ['Artifact validation: Saved-fit or eligibility validation did not pass']))
    manifest = dict(jobs=jobs, source_sha256={p.name: sha256(p) for p in (source / 'scripts').iterdir()})
    (source / 'manifest.json').write_text(json.dumps(manifest))
    (audit / 'source_manifest.json').write_bytes((source / 'manifest.json').read_bytes())
    (audit / 'review_summary.json').write_text(json.dumps(dict(source_run=str(source), results=reviews)))
    (audit / 'postrun_summary.json').write_text(json.dumps(dict(listeria_status='PASS', container_unchanged=True,
                                                              container_sha256=sha256(root / 'foodnet.sif'))))
    return root, audit, source


class SamplerLauncherTests(unittest.TestCase):
    def test_checkpoint_recovery_disables_sampling_and_verifies_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);root,audit,source=fixture(base);previous=base/'previous'
            launcher.prepare(root,audit,previous)
            plan=json.loads((previous/'manifest.json').read_text())
            for j in plan['jobs']:
                work=previous/j['task'];(work/'checkpoints').mkdir()
                f=work/'checkpoints'/(j['prefix']+'.rds');f.write_bytes(b'completed fake checkpoint')
                (work/(j['prefix']+'_identity_check.json')).write_text(json.dumps(dict(checkpoint_sha256=sha256(f))))
            dest=base/'recovery';self.assertEqual(launcher.recover(root,previous,dest),2)
            for j in plan['jobs']:
                work=dest/j['task']
                self.assertIn('FOODNET_CHECKPOINT_ONLY=1',(work/'run.sh').read_text())
                self.assertEqual((work/'checkpoints'/(j['prefix']+'.rds')).read_bytes(),b'completed fake checkpoint')
                subprocess.check_call(['bash','-n',str(work/'run.sh')])
            f.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'Checkpoint hash'):launcher.recover(root,previous,base/'bad')

    def test_only_divergence_models_and_saved_model_commands(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); root, audit, source = fixture(base); dest = base / 'new run'
            original = {str(p.relative_to(source)): p.read_bytes() for p in source.rglob('*') if p.is_file()}
            self.assertEqual(launcher.prepare(root, audit, dest), 2)
            plan = json.loads((dest / 'manifest.json').read_text())
            self.assertEqual([j['prefix'] for j in plan['jobs']], ['SHIGELLA_combined', 'VIBRIO_combined'])
            self.assertEqual(plan['retained_passing_models'], ['CAMPYLOBACTER_combined'])
            for job in plan['jobs']:
                self.assertEqual(job['adapt_delta'], '0.9999')
                args = job['sampler_refit_command']
                self.assertIn(str(source) + ':' + str(source) + ':ro', args)
                self.assertEqual(args[args.index('--env') + 1], 'OPENBLAS_NUM_THREADS=2,OMP_NUM_THREADS=2,MKL_NUM_THREADS=2')
                script = (dest / job['task'] / 'run.sh').read_text()
                self.assertIn('refit_surveillance_sampler.R', script)
                self.assertIn('audit_saved_state_fit.R', script)
                for forbidden in ('trendy.R', 'clean.csv', '--mmwrFile', '--censusFileB', '--cleanFile'):
                    self.assertNotIn(forbidden, script)
                self.assertEqual((dest / job['task'] / 'functions.R').read_bytes(), (source / 'scripts/functions.R').read_bytes())
            for path in dest.rglob('*.sh'): subprocess.check_call(['bash', '-n', str(path)])
            self.assertEqual(original, {str(p.relative_to(source)): p.read_bytes() for p in source.rglob('*') if p.is_file()})

    def test_hash_mismatches_reject_before_submission(self):
        for variant in ('container', 'selected_fit', 'retained_fit', 'source_snapshot'):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp:
                base = Path(temp); root, audit, source = fixture(base)
                target = {'container': root / 'foodnet.sif',
                          'selected_fit': source / 'task_01/spline_results/SHIGELLA_combined_brm.Rds',
                          'retained_fit': source / 'task_02/spline_results/CAMPYLOBACTER_combined_brm.Rds',
                          'source_snapshot': source / 'scripts/functions.R'}[variant]
                target.write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'differs|changed'):
                    launcher.prepare(root, audit, base / 'new')

    def test_changed_manifest_or_failed_retained_artifacts_are_rejected(self):
        for variant in ('manifest', 'retained_artifacts'):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp:
                base = Path(temp); root, audit, source = fixture(base)
                if variant == 'manifest':
                    path = source / 'manifest.json'; obj = json.loads(path.read_text())
                    obj['jobs'][0]['first_year'] = 2000
                else:
                    path = audit / 'review_summary.json'; obj = json.loads(path.read_text())
                    obj['results'][1]['status'] = 'REVIEW_REQUIRED'
                    obj['results'][1]['issues'] = ['Missing site-year results']
                path.write_text(json.dumps(obj))
                with self.assertRaisesRegex(ValueError, 'manifest|artifact'):
                    launcher.prepare(root, audit, base / 'new')

    def test_worker_integrity_check_precedes_any_container_invocation(self):
        for changed in (False, True):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as temp:
                base = Path(temp); root, audit, _ = fixture(base); dest = base / 'new run'
                launcher.prepare(root, audit, dest)
                if changed: (dest / 'scripts/refit_surveillance_sampler.R').write_text('# changed after planning')
                fake = base / 'fakebin'; fake.mkdir(); runtime = fake / 'singularity'
                runtime.write_text('#!/bin/bash\nprintf "called\\n" >> "$CALLS"\nexit 0\n'); runtime.chmod(0o755)
                calls = base / 'calls.txt'; work = dest / 'task_01'
                result = subprocess.run(['bash', str(work / 'run.sh')],
                    env=dict(os.environ, PATH=str(fake) + ':' + os.environ['PATH'], CALLS=str(calls)),
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                self.assertEqual(result.returncode, 1 if changed else 0, result.stderr)
                self.assertEqual((work / 'exit_status.txt').read_text().strip(), '1' if changed else '0')
                if changed: self.assertFalse(calls.exists())
                else: self.assertEqual(calls.read_text().splitlines(), ['called', 'called'])

    def test_other_audit_failures_are_not_sampler_retries(self):
        for variant in ('eligibility', 'extra_issue', 'listeria', 'container_stability'):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp:
                base = Path(temp); root, audit, _ = fixture(base)
                if variant in ('eligibility', 'extra_issue'):
                    path = audit / 'task_01/saved_fit_validation.json'; obj = json.loads(path.read_text())
                    if variant == 'eligibility': obj['eligibility_status'] = 'REVIEW_REQUIRED'
                    else: obj['issues'].append('Low tail ESS')
                else:
                    path = audit / 'postrun_summary.json'; obj = json.loads(path.read_text())
                    obj['listeria_status' if variant == 'listeria' else 'container_unchanged'] = 'REVIEW_REQUIRED' if variant == 'listeria' else False
                path.write_text(json.dumps(obj))
                with self.assertRaises(ValueError): launcher.prepare(root, audit, base / 'new')

    def test_missing_required_inputs_stop_planning(self):
        for variant in ('review', 'proof', 'selected_fit', 'classification', 'auditor', 'container'):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp:
                base = Path(temp); root, audit, source = fixture(base)
                target = {'review': audit / 'review_summary.json', 'proof': audit / 'task_01/saved_fit_validation.json',
                          'selected_fit': source / 'task_01/spline_results/SHIGELLA_combined_brm.Rds',
                          'classification': source / 'task_01/classification_rules.csv',
                          'auditor': root / 'scripts/audit_saved_state_fit.R', 'container': root / 'foodnet.sif'}[variant]
                target.unlink()
                with self.assertRaises((OSError, ValueError)):
                    launcher.prepare(root, audit, base / 'new')

    def test_no_unnecessary_work_if_all_models_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); root, audit, _ = fixture(base)
            for path in audit.glob('task_*/saved_fit_validation.json'):
                obj = json.loads(path.read_text()); obj.update(status='PASS', issues=[])
                path.write_text(json.dumps(obj))
            review_path = audit / 'review_summary.json'; review = json.loads(review_path.read_text())
            for row in review['results']: row.update(status='CHECKS_PASS', issues=[])
            review_path.write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError, 'No divergence'):
                launcher.prepare(root, audit, base / 'new')


if __name__ == '__main__': unittest.main()
