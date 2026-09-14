import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import review_monthly_factorial as review


def write_rows(path, rows):
    review.write_csv(path, rows)


def seal(root):
    manifest = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in root.rglob('*') if p.is_file() and p.name != 'report_sha256.json'}
    (root/'report_sha256.json').write_text(json.dumps(manifest))


def fixture(root, missing=None):
    root.mkdir()
    specs = [dict(id=k, **v) for k, v in review.matrix().items()]
    snapshot = root/'scripts/launch_monthly_factorial.py'
    snapshot.parent.mkdir()
    snapshot.write_text('# synthetic snapshot\n')
    plan = dict(version='monthly_factorial_v1', verified=True, accepted=False,
                independent_validation=False, coverage_certified=False, cpo_ranking=False,
                new_fits=48, reused_fits=60, total_cells=108,
                inputs={'/synthetic/run/scripts/launch_monthly_factorial.py': hashlib.sha256(snapshot.read_bytes()).hexdigest()},
                tasks=[t for t in specs if not t['reused']], references=[t for t in specs if t['reused']])
    for t in plan['references']:
        t['reference'] = dict(truth_sha256='a'*64)
    (root/'plan.json').write_text(json.dumps(plan))
    digest = hashlib.sha256((root/'plan.json').read_bytes()).hexdigest()
    records, scores, tails = [], [], []
    for t in specs:
        success = t['id'] != missing
        records.append(dict(task=t['id'], status='COMPLETE' if success else 'FAILED_OR_MISSING', reused=t['reused']))
        if not success:
            continue
        if not t['reused']:
            work = root/t['id']
            work.mkdir()
            (work/'task_status.json').write_text(json.dumps(dict(task=t['id'], status='COMPLETE', exit_status=0, plan_sha256=digest, truth_sha256='a'*64, outputs={})))
        base = {k: v for k, v in t.items() if k in ('pathogen', 'cutoff', 'temporal', 'seasonal', 'reused')}
        for y in range(t['cutoff']+1, t['cutoff']+4):
            for stream in range(5):
                r = dict(base, task=t['id'], year=y, stream=stream, draws=8000 if stream == 0 else 2000)
                a, b = t['temporal'] == 'ar1', t['seasonal']
                score = -5 + a*.1 + b*.2 + a*b*.3 + stream*.001
                for state in review.STATES:
                    scores.append(dict(r, state=state, mean_log_score=score, max_cell_density_relative_mcse=.01))
                for state in review.STATES+('ALL',):
                    n = 1000 if state == 'ALL' else 100
                    tails.append(dict(r, state=state, observed=n, mean_expected=n*1.1, median_expected=n, p975_expected=n*1.5, max_expected=n*2, top_one_percent_mean_share=.05, lower95=n*.8, median_predictive=n, upper95=n*1.5, prob_above_twice_observed=.01))
    for t in specs:
        if t['id'] == missing:
            continue
        folder = root/'references'/t['id'] if t['reused'] else root/t['id']/'result'
        folder.mkdir(parents=True, exist_ok=True)
        for name, data in (('stream_scores.csv', scores), ('aggregate_tails.csv', tails)):
            portable = [{k:v for k,v in r.items() if k not in ('task','pathogen','cutoff','temporal','seasonal','reused')} for r in data if r['task'] == t['id']]
            write_rows(folder/name, portable)
            if t['reused']:
                plan['inputs']['/synthetic/run/'+str((folder/name).relative_to(root))] = hashlib.sha256((folder/name).read_bytes()).hexdigest()
    (root/'plan.json').write_text(json.dumps(plan))
    digest = hashlib.sha256((root/'plan.json').read_bytes()).hexdigest()
    for t in specs:
        if not t['reused'] and t['id'] != missing:
            record_path = root/t['id']/'task_status.json'
            record = json.loads(record_path.read_text()); record['plan_sha256'] = digest
            record_path.write_text(json.dumps(record))
    summary = dict(tasks=records, issues=[], complete=108-(missing is not None), expected=108, new_fits=48, reused_fits=60, accepted=False, independent_validation=False, cpo_ranking=False)
    (root/'summary.json').write_text(json.dumps(summary))
    write_rows(root/'all_stream_scores.csv', scores)
    write_rows(root/'all_aggregate_tails.csv', tails)
    site, equal = review.recompute(scores, set())
    write_rows(root/'factorial_site_contrasts.csv', site)
    write_rows(root/'factorial_equal_site_contrasts.csv', equal)
    seal(root)


class FactorialReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)/'report'
        fixture(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def output(self):
        return Path(self.temp.name)/'out'

    def change_csv(self, name, action):
        with (self.root/name).open() as f:
            rows = list(csv.DictReader(f))
        action(rows)
        write_rows(self.root/name, rows)
        seal(self.root)

    def test_full_108_archive_and_numeric_contrasts(self):
        archive = Path(self.temp.name)/'report.tar.gz'
        with tarfile.open(str(archive), 'w:gz') as tar:
            for p in self.root.rglob('*'):
                if p.is_file():
                    tar.add(str(p), arcname=str(p.relative_to(self.root)))
        result = review.review(archive, self.output(), False)
        self.assertEqual(result['status'], 'COMPLETE_EXPLORATORY')
        self.assertEqual((result['new_complete'], result['reused_complete']), (48, 60))
        with (self.output()/'pooled_component_review.csv').open() as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 81)
        self.assertAlmostEqual(float(rows[0]['interaction']), .3)
        self.assertAlmostEqual(float(rows[0]['seasonality_under_ar1']), .5)
        self.assertFalse(result['accepted'])
        with (self.output()/'pooled_calibration.csv').open() as f:
            r = next(csv.DictReader(f))
        self.assertAlmostEqual(float(r['equal_site_relative_bias']), .1)
        self.assertEqual(float(r['site_coverage_fraction']), 1.)

    def test_partial_missing_arm_keeps_other_blocks(self):
        import shutil
        shutil.rmtree(str(self.root))
        fixture(self.root, 'SALMONELLA_2011_ar1_nonseasonal')
        result = review.review(self.root, self.output(), False)
        self.assertEqual(result['status'], 'PARTIAL_EXPLORATORY')
        self.assertEqual(result['complete'], 107)
        with (self.output()/'pooled_component_review.csv').open() as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 78)

    def test_collector_issue_blocks_numeric_exports(self):
        p = self.root/'summary.json'
        data = json.loads(p.read_text()); data['issues'] = ['Changed source artifact']
        p.write_text(json.dumps(data)); seal(self.root)
        result = review.review(self.root, self.output(), False)
        self.assertFalse(result['comparisons_interpretable'])
        self.assertFalse((self.output()/'pooled_component_review.csv').exists())

    def test_paired_truth_mismatch_blocks_interpretation(self):
        path = next(self.root.glob('CAMPYLOBACTER_2011_ar1_nonseasonal/task_status.json'))
        record = json.loads(path.read_text()); record['truth_sha256'] = 'b'*64
        path.write_text(json.dumps(record)); seal(self.root)
        result = review.review(self.root, self.output(), False)
        self.assertEqual(result['status'], 'BLOCKED_COLLECTOR_OR_TRUTH_ISSUES')
        self.assertFalse((self.output()/'pooled_component_review.csv').exists())

    def test_collector_issue_with_suppressed_contrasts(self):
        p = self.root/'summary.json'
        obj = json.loads(p.read_text()); obj['issues'] = ['Global verification failure']
        p.write_text(json.dumps(obj))
        (self.root/'factorial_site_contrasts.csv').unlink()
        (self.root/'factorial_equal_site_contrasts.csv').unlink()
        seal(self.root)
        result = review.review(self.root, self.output(), False)
        self.assertFalse(result['comparisons_interpretable'])

    def test_duplicate_metric_rejected(self):
        self.change_csv('all_stream_scores.csv', lambda rows: rows.append(dict(rows[0])))
        with self.assertRaisesRegex(ValueError, 'Duplicate metric'):
            review.review(self.root, self.output(), False)

    def test_nonfinite_metric_rejected(self):
        self.change_csv('all_stream_scores.csv', lambda rows: rows[0].update(mean_log_score='NaN'))
        with self.assertRaisesRegex(ValueError, 'Nonfinite'):
            review.review(self.root, self.output(), False)

    def test_false_seasonal_label_rejected(self):
        self.change_csv('all_stream_scores.csv', lambda rows: rows[0].update(seasonal='True'))
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            review.review(self.root, self.output(), False)

    def test_tampered_manifest_rejected(self):
        with (self.root/'all_stream_scores.csv').open('a') as f:
            f.write('tampered\n')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            review.review(self.root, self.output(), False)

    def test_fresh_manifest_does_not_override_plan_binding(self):
        (self.root/'scripts/launch_monthly_factorial.py').write_text('changed\n')
        seal(self.root)
        with self.assertRaisesRegex(ValueError, 'plan-bound snapshot'):
            review.review(self.root, self.output(), False)

    def test_regenerated_merged_reports_must_match_task_reports(self):
        self.change_csv('all_stream_scores.csv', lambda rows: rows[0].update(mean_log_score='-9'))
        with self.assertRaisesRegex(ValueError, 'per-task values'):
            review.review(self.root, self.output(), False)

    def test_wrong_published_contrast_rejected(self):
        self.change_csv('factorial_equal_site_contrasts.csv', lambda rows: rows[0].update(interaction='99'))
        with self.assertRaisesRegex(ValueError, 'differs from recomputation'):
            review.review(self.root, self.output(), False)

    def test_invalid_total_rejected(self):
        self.change_csv('all_aggregate_tails.csv', lambda rows: rows[10].update(observed='999'))
        with self.assertRaisesRegex(ValueError, 'total differs|per-task values'):
            review.review(self.root, self.output(), False)

    def test_incomplete_grid_rejected(self):
        self.change_csv('all_aggregate_tails.csv', lambda rows: rows.pop())
        with self.assertRaisesRegex(ValueError, 'Incomplete metric grid'):
            review.review(self.root, self.output(), False)

    def test_malformed_csv_rejected(self):
        p = self.root/'all_stream_scores.csv'
        with p.open('a') as f: f.write('bad,row\n')
        seal(self.root)
        with self.assertRaisesRegex(ValueError, 'Malformed CSV'):
            review.review(self.root, self.output(), False)

    def test_path_traversal_and_symlinks_rejected(self):
        archive = Path(self.temp.name)/'evil.tar'
        for name, kind in (('../escape', tarfile.REGTYPE), ('evil', tarfile.SYMTYPE)):
            with tarfile.open(str(archive), 'w') as tar:
                item = tarfile.TarInfo(name); item.type = kind
                tar.addfile(item, io.BytesIO(b''))
            with self.assertRaises(ValueError):
                review.Report(archive)
        (self.root/'link').symlink_to(self.root/'summary.json')
        with self.assertRaisesRegex(ValueError, 'Symlinks'):
            review.Report(self.root)

    def test_acceptance_claim_rejected(self):
        p = self.root/'summary.json'
        obj = json.loads(p.read_text()); obj['accepted'] = True
        p.write_text(json.dumps(obj)); seal(self.root)
        with self.assertRaisesRegex(ValueError, 'Unsupported claim'):
            review.review(self.root, self.output(), False)


if __name__ == '__main__':
    unittest.main()
