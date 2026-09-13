"""Plan and gate tests with synthetic files and local stub commands only."""
import contextlib
import fcntl
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import launch_county_forecast_validation as launcher
import run_county_forecast_validation as runner


def fixture_root(base):
    root = base / 'checkout'; (root / 'scripts').mkdir(parents=True); (root / 'tests').mkdir()
    for name in launcher.SCRIPTS:
        src = ROOT / 'scripts' / name
        (root / 'scripts' / name).write_bytes(src.read_bytes() if src.exists() else b'# synthetic planning-only placeholder\n')
    for name in ('test_county_forecast_invariance.R', 'test_county_historical_reference.R'):
        src = ROOT / 'tests' / name
        (root / 'tests' / name).write_bytes(src.read_bytes() if src.exists() else b'# synthetic planning-only placeholder\n')
    container = root / 'foodnet-inla-fixed.sif'; container.write_bytes(b'synthetic image')
    return root, container


class ForecastValidationLauncherTests(unittest.TestCase):
    def test_fixed_matrix_parallel_groups_and_readonly_preparation(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); root, container = fixture_root(base); dest = base / 'plan with spaces'
            plan = launcher.prepare(root, dest, container, verify=False, replicates=20)
            self.assertEqual(sum(t['kind'] == 'calibration' for t in plan['tasks']), 80)
            self.assertEqual(sum(t['kind'] == 'forecast' for t in plan['tasks']), 54)
            self.assertEqual(sum(t['kind'] == 'horizon' for t in plan['tasks']), 1)
            self.assertEqual(len({t['id'] for t in plan['tasks']}), len(plan['tasks']))
            self.assertFalse(plan['inputs_verified']); self.assertTrue(plan['no_state_model_reruns'])
            self.assertTrue(plan['no_dashboard_promotion'])
            for task in plan['tasks']:
                args = task['command']; self.assertIn('--cleanenv', args); self.assertIn('--env', args)
                self.assertNotIn('nextflow', args)
                if task['kind'] == 'forecast':
                    self.assertEqual(task['horizon'], 3)
                    self.assertIn('run_county_forecast_comparison.R', ' '.join(args))
            for script in dest.glob('*.sh'): subprocess.check_call(['bash', '-n', str(script)])
            self.assertIn('-hold_jid', (ROOT / 'scripts/launch_county_forecast_validation.py').read_text())
            self.assertEqual(container.read_bytes(), b'synthetic image')

    def test_gate_denies_unverified_and_incomplete_prerequisites(self):
        for case in ('unverified', 'incomplete'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                base = Path(temp); root, container = fixture_root(base); dest = base / 'plan'
                plan = launcher.prepare(root, dest, container, verify=False, replicates=20)
                if case == 'incomplete':
                    plan['inputs_verified'] = True; (dest / 'manifest.json').write_text(json.dumps(plan))
                else:
                    for task in plan['tasks']:
                        if task['kind'] == 'forecast': continue
                        work = dest / task['id']; work.mkdir(exist_ok=True)
                        (work / 'task_status.json').write_text(json.dumps(dict(status='COMPLETE', exit_status=0)))
                result = subprocess.run([sys.executable, str(dest / 'scripts/gate.py'), str(dest)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                gate = json.loads((dest / 'gate.json').read_text())
                self.assertNotEqual(gate['status'], 'PASS')
                self.assertEqual(gate['manifest_sha256'], runner.sha(dest / 'manifest.json'))

    def test_real_command_never_runs_without_current_successful_gate(self):
        for case in ('missing', 'failed', 'different_manifest'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                dest = Path(temp); marker = dest / 'command_was_run'
                task = dict(id='real', kind='forecast', command=[sys.executable, '-c',
                    'from pathlib import Path; Path(' + repr(str(marker)) + ').write_text("bad")'])
                manifest = dest / 'manifest.json'; manifest.write_text(json.dumps(dict(tasks=[task], fingerprints={})))
                if case != 'missing':
                    (dest / 'gate.json').write_text(json.dumps(dict(status='PASS' if case == 'different_manifest' else 'REVIEW_REQUIRED',
                        manifest_sha256='different' if case == 'different_manifest' else runner.sha(manifest))))
                self.assertNotEqual(runner.run(dest, 'real'), 0)
                self.assertFalse(marker.exists())

    def test_unrelated_artifact_cannot_certify_task_success(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp); task = dict(id='simulation', kind='calibration', density='sparse', variant='iid', replicate=1,
                command=[sys.executable, '-c', 'from pathlib import Path; Path("simulation/sessionInfo.txt").write_text("not a result")'])
            (dest / 'manifest.json').write_text(json.dumps(dict(tasks=[task], fingerprints={})))
            self.assertNotEqual(runner.run(dest, task['id']), 0)
            status = json.loads((dest / task['id'] / 'task_status.json').read_text())
            self.assertNotEqual(status['status'], 'COMPLETE')

    def test_completed_reuse_revalidates_artifacts_without_reexecuting(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp)
            command = ('from pathlib import Path; p=Path("horizon/result"); p.mkdir(parents=True); '
                'p.joinpath("status.txt").write_text("HORIZON_INVARIANCE_PASS\\n"); '
                'p.joinpath("checks.csv").write_text("check,pass,status\\n" + '
                '"".join(n+",TRUE,PASS\\n" for n in ["spatial_baseline","spatial_county_time","iid_baseline","iid_county_time"]))')
            task = dict(id='horizon', kind='horizon', command=[sys.executable, '-c', command])
            (dest / 'manifest.json').write_text(json.dumps(dict(tasks=[task], fingerprints={})))
            self.assertEqual(runner.run(dest, 'horizon'), 0)
            status = dest / 'horizon/task_status.json'; before = status.read_bytes()
            self.assertEqual(runner.run(dest, 'horizon'), 0)
            self.assertEqual(before, status.read_bytes())
            checks = dest / 'horizon/result/checks.csv'
            checks.write_text(checks.read_text().replace('TRUE', 'FALSE', 1))
            recorded = json.loads(status.read_text()); recorded['outputs']['result/checks.csv'] = runner.sha(checks)
            status.write_text(json.dumps(recorded))
            with self.assertRaises(ValueError): runner.run(dest, 'horizon')

    def test_exclusive_task_lock_preserves_active_attempt(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp); work = dest / 'active'; work.mkdir()
            task = dict(id='active', kind='horizon', command=[sys.executable, '-c', 'raise RuntimeError("must not execute")'])
            (dest / 'manifest.json').write_text(json.dumps(dict(tasks=[task], fingerprints={})))
            status = work / 'task_status.json'; status.write_text('{"status":"RUNNING"}')
            evidence = work / 'in_progress.txt'; evidence.write_text('owned by first runner')
            with (work / '.task.lock').open('a') as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaisesRegex(ValueError, 'active runner'): runner.run(dest, 'active')
            self.assertEqual(status.read_text(), '{"status":"RUNNING"}')
            self.assertEqual(evidence.read_text(), 'owned by first runner')
            self.assertFalse((work / 'task.log').exists())

    def test_too_few_calibration_replicates_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); root, container = fixture_root(base)
            with self.assertRaisesRegex(ValueError, '20'):
                launcher.prepare(root, base / 'plan', container, verify=False, replicates=19)


if __name__ == '__main__': unittest.main()
