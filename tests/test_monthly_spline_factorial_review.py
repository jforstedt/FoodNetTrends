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
import review_monthly_spline_factorial as spline
import review_monthly_factorial as review
import shutil


def write_rows(path, rows):
    review.write_csv(path, rows)


def seal(root):
    manifest = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in root.rglob('*') if p.is_file() and p.name != 'report_sha256.json'}
    (root/'report_sha256.json').write_text(json.dumps(manifest))


def fixture(root, missing=None):
    root.mkdir()
    specs = [dict(id=k, seed=4000, **v) for k, v in spline.matrix().items()]
    snapshot = root/'scripts/launch_monthly_spline_factorial.py'
    snapshot.parent.mkdir()
    snapshot.write_text('# synthetic snapshot\n')
    plan = dict(version='monthly_spline_factorial_v1', verified=True, accepted=False,
                independent_validation=False, coverage_certified=False, cpo_ranking=False,
                new_fits=54, reused_fits=108, total_cells=162,
                inputs={'/synthetic/run/scripts/launch_monthly_spline_factorial.py': hashlib.sha256(snapshot.read_bytes()).hexdigest()},
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
                score = -5 + a*.1 + b*.2 + a*b*.3 + stream*.001 + (t['temporal']=='spline')*(.4+b*.5)
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
    repository = Path(__file__).resolve().parents[1]
    shutil.copytree(str(repository/'analysis_configs/monthly_spline_basis'), str(root/'basis'))
    for name in ('prepare_monthly_spline_basis.R', 'monthly_spline_combination.R', 'county_spline_candidate.R'):
        shutil.copyfile(str(repository/'scripts'/name), str(root/'scripts'/name))
    for t in specs:
        if t['id'] == missing:
            continue
        folder = root/'references'/t['id'] if t['reused'] else root/t['id']/'result'
        write_rows(folder/'settings.csv', [dict(cutoff=t['cutoff'], seasonal=t['seasonal'], streams=4, draws_per_stream=2000, coverage_certified=False, refitted=False, base_seed=4000)])
        if not t['reused']:
            write_rows(folder/'sensitivity_settings.csv', [dict(temporal_model='spline', comparison='monthly_spline_factorial_v1', seasonal=t['seasonal'], end_year=t['end_year'], rate_center=.0002, k=6, slope_sd=.5, nonlinear_sd_upper=.5)])
            (root/t['id']/'task.log').write_text('Synthetic completion\n')
    for path in root.rglob('*'):
        if path.is_file() and str(path.relative_to(root)).startswith(('scripts/', 'basis/', 'references/')):
            plan['inputs']['/synthetic/run/'+str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    (root/'plan.json').write_text(json.dumps(plan))
    digest = hashlib.sha256((root/'plan.json').read_bytes()).hexdigest()
    for t in specs:
        if not t['reused'] and t['id'] != missing:
            record_path = root/t['id']/'task_status.json'
            record = json.loads(record_path.read_text()); record['plan_sha256'] = digest
            record['outputs'] = {str(p.relative_to(root/t['id'])):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/t['id']).rglob('*') if p.is_file() and p.name != 'task_status.json'}
            record_path.write_text(json.dumps(record))
    summary = dict(tasks=records, issues=[], complete=162-(missing is not None), expected=162, new_fits=54, reused_fits=108, accepted=False, independent_validation=False, cpo_ranking=False)
    (root/'summary.json').write_text(json.dumps(summary))
    write_rows(root/'all_stream_scores.csv', scores)
    write_rows(root/'all_aggregate_tails.csv', tails)
    site, equal = spline.recompute(scores, set())
    write_rows(root/'spline_site_contrasts.csv', site)
    write_rows(root/'spline_equal_site_contrasts.csv', equal)
    seal(root)


class SplineReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)/'report'
        fixture(self.root)
        self.out = Path(self.temp.name)/'review'

    def tearDown(self):
        self.temp.cleanup()

    def change(self, filename, action):
        path = self.root/filename
        with path.open() as f: data = list(csv.DictReader(f))
        action(data); write_rows(path, data); seal(self.root)

    def test_full_archive_both_references_and_six_arms(self):
        archive = Path(self.temp.name)/'report.tar.gz'
        with tarfile.open(str(archive), 'w:gz') as tar:
            for p in self.root.rglob('*'):
                if p.is_file(): tar.add(str(p), arcname=str(p.relative_to(self.root)))
        result = spline.review(archive, self.out, False)
        self.assertEqual((result['complete'],result['new_complete'],result['reused_complete']), (162,54,108))
        self.assertEqual(result['complete_four_arm_blocks'],54)
        with (self.out/'pooled_component_review.csv').open() as f: rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),162)
        for r in rows:
            self.assertAlmostEqual(float(r['interaction']), .5 if r['reference']=='rw1' else .2)
            self.assertAlmostEqual(float(r['spline_minus_reference_nonseasonal']), .4 if r['reference']=='rw1' else .3)
            self.assertAlmostEqual(float(r['spline_minus_reference_seasonal']), .9 if r['reference']=='rw1' else .5)
        with (self.out/'pooled_arm_scores.csv').open() as f: arms=list(csv.DictReader(f))
        self.assertEqual(len(arms),486)
        self.assertEqual({r['temporal'] for r in arms},{'spline','rw1','ar1'})

    def test_partial_explicit_missing_blocks(self):
        shutil.rmtree(str(self.root)); fixture(self.root,'SALMONELLA_2011_spline_seasonal')
        result = spline.review(self.root,self.out,False)
        self.assertEqual(result['status'],'PARTIAL_EXPLORATORY')
        self.assertEqual(result['complete_four_arm_blocks'],52)
        with (self.out/'comparison_block_inventory.csv').open() as f: rows=list(csv.DictReader(f))
        self.assertEqual(sum(r['complete']=='False' for r in rows),2)

    def test_integrity_issue_suppresses_all_numeric_exports(self):
        p=self.root/'summary.json'; data=json.loads(p.read_text());data['issues']=['Changed source'];p.write_text(json.dumps(data));seal(self.root)
        result=spline.review(self.root,self.out,False)
        self.assertFalse(result['comparisons_interpretable'])
        self.assertFalse((self.out/'pooled_arm_scores.csv').exists())

    def test_changed_basis_fresh_manifest_still_rejected(self):
        p=self.root/'basis/2011.csv';p.write_text(p.read_text().replace('0.102053','0.902053'));seal(self.root)
        with self.assertRaisesRegex(ValueError,'plan-bound snapshot'): spline.review(self.root,self.out,False)

    def test_basis_recipe_binding_checked_even_with_new_plan_hash(self):
        p=self.root/'basis/2011.csv';p.write_text(p.read_text().replace('0.102053','0.902053'))
        planpath=self.root/'plan.json';plan=json.loads(planpath.read_text());plan['inputs']['/synthetic/run/basis/2011.csv']=hashlib.sha256(p.read_bytes()).hexdigest();planpath.write_text(json.dumps(plan))
        for p in self.root.glob('*/task_status.json'):
            r=json.loads(p.read_text());r['plan_sha256']=hashlib.sha256(planpath.read_bytes()).hexdigest();p.write_text(json.dumps(r))
        seal(self.root)
        with self.assertRaisesRegex(ValueError,'Prepared basis binding'): spline.review(self.root,self.out,False)

    def test_merged_score_tampering_rejected(self):
        self.change('all_stream_scores.csv',lambda rows:rows[0].update(mean_log_score='-9'))
        with self.assertRaisesRegex(ValueError,'per-task values'): spline.review(self.root,self.out,False)

    def test_duplicate_cells_rejected(self):
        self.change('all_stream_scores.csv',lambda rows:rows.append(dict(rows[0])))
        with self.assertRaisesRegex(ValueError,'Duplicate metric'): spline.review(self.root,self.out,False)

    def test_published_reference_mismatch_rejected(self):
        self.change('spline_equal_site_contrasts.csv',lambda rows:rows[0].update(reference='spline'))
        with self.assertRaisesRegex(ValueError,'contrast domain'): spline.review(self.root,self.out,False)

    def test_missing_task_output_binding_rejected(self):
        p=next(self.root.glob('*spline*/task_status.json'));r=json.loads(p.read_text());r['outputs']={};p.write_text(json.dumps(r));seal(self.root)
        with self.assertRaisesRegex(ValueError,'Missing task-bound'): spline.review(self.root,self.out,False)

    def test_truth_mismatch_blocks_exports(self):
        p=next(self.root.glob('*spline*/task_status.json'));r=json.loads(p.read_text());r['truth_sha256']='b'*64;p.write_text(json.dumps(r));seal(self.root)
        result=spline.review(self.root,self.out,False)
        self.assertFalse(result['comparisons_interpretable'])
        self.assertFalse((self.out/'pooled_component_review.csv').exists())

    def test_unbound_copied_reference_rejected(self):
        p=next((self.root/'references').glob('*/settings.csv'));p.write_text(p.read_text()+'\n');seal(self.root)
        with self.assertRaisesRegex(ValueError,'plan-bound snapshot'): spline.review(self.root,self.out,False)

    def test_changed_sampling_protocol_rejected(self):
        work=next(self.root.glob('*spline*/result'))
        (work/'rng_protocol.csv').write_text('protocol\nfuture_v2\n');seal(self.root)
        with self.assertRaisesRegex(ValueError,'sampling-protocol change'): spline.review(self.root,self.out,False)

    def test_missing_complete_grid_rejected(self):
        self.change('all_aggregate_tails.csv',lambda rows:rows.pop())
        with self.assertRaisesRegex(ValueError,'Incomplete metric grid'): spline.review(self.root,self.out,False)

if __name__=='__main__': unittest.main()
