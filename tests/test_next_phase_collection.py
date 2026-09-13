"""Exercise final collection with partial HPC failure and revoked artifacts."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from collect_next_phase_batch import collect
from run_next_phase_task import sha


class CollectionTests(unittest.TestCase):
    def fixture(self, root):
        task = dict(id='gate', kind='gate')
        (root / 'plan.json').write_text(json.dumps(dict(tasks=[task], fingerprints={}, verified=True)))
        out = root / 'gate/result'
        out.mkdir(parents=True)
        (out / 'status.txt').write_text('SPLINE_NUMERICAL_GATE_PASS\n')
        (out / 'spline_gate_checks.csv').write_text('model,standardized_mean_change,relative_sd_change,heldout_mask_change,status\niid,0,0,0,PASS\nspatial,0,0,0,PASS\n')
        (out / 'spline_gaussian_reference.csv').write_text('mean_error,sd_error,status\n0,0,PASS\n')
        record = dict(status='COMPLETE', exit_status=0,
                      outputs={str(p.relative_to(root / 'gate')): sha(p) for p in out.iterdir()})
        (root / 'gate/task_status.json').write_text(json.dumps(record))
        return record

    def run_collect(self, root):
        with contextlib.redirect_stdout(io.StringIO()):
            code = collect(root)
        summary = json.loads((root / 'summary.json').read_text())
        with tarfile.open(str(root) + '.tar.gz') as archive:
            names = archive.getnames()
        self.assertIn('summary.json', names)
        return code, summary, names

    def test_success_still_requires_scientific_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'run'; root.mkdir(); self.fixture(root)
            (root / 'gate/result/fit_INTERNAL.rds').write_bytes(b'large checkpoint placeholder')
            code, summary, names = self.run_collect(root)
            self.assertEqual(code, 0)
            self.assertTrue(summary['execution_complete'])
            self.assertEqual(summary['scientific_status'], 'REVIEW_REQUIRED')
            self.assertFalse(any(n.endswith('.rds') for n in names))

    def test_missing_and_failed_tasks_preserved_in_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'run'; root.mkdir(); self.fixture(root)
            plan = json.loads((root / 'plan.json').read_text())
            plan['tasks'] += [dict(id='missing', kind='sampling'), dict(id='failed', kind='cyclospora')]
            (root / 'plan.json').write_text(json.dumps(plan))
            (root / 'failed').mkdir()
            (root / 'failed/task_status.json').write_text(json.dumps(dict(status='FAILED', exit_status=1, reason='synthetic failure')))
            (root / 'failed/task.log').write_text('synthetic failure detail\n')
            code, summary, names = self.run_collect(root)
            self.assertEqual(code, 1)
            self.assertFalse(summary['execution_complete'])
            self.assertEqual([t['status'] for t in summary['tasks']], ['COMPLETE', 'MISSING_OR_INVALID', 'FAILED'])
            self.assertIn('failed/task.log', names)

    def test_changed_output_revokes_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'run'; root.mkdir(); self.fixture(root)
            with (root / 'gate/result/status.txt').open('a') as f: f.write('changed after completion\n')
            code, summary, _ = self.run_collect(root)
            self.assertEqual(code, 1)
            self.assertEqual(summary['tasks'][0]['status'], 'MISSING_OR_INVALID')
            self.assertIn('fingerprint', summary['tasks'][0]['reason'])

    def test_nonzero_exit_cannot_claim_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'run'; root.mkdir(); record = self.fixture(root)
            record['exit_status'] = 140
            (root / 'gate/task_status.json').write_text(json.dumps(record))
            code, summary, _ = self.run_collect(root)
            self.assertEqual(code, 1)
            self.assertFalse(summary['execution_complete'])


if __name__ == '__main__': unittest.main()
