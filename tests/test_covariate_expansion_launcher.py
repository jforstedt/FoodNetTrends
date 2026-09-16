import copy
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import launch_covariate_expansion as m


class ExpansionLauncherTests(unittest.TestCase):
    def test_matrix_preserves_complete_factorials_and_no_pilot_refits(self):
        tasks = m.matrix()
        self.assertEqual(len(tasks), 288)
        self.assertEqual(len({t['task_id'] for t in tasks}), 288)
        self.assertEqual(len({t['seed'] for t in tasks}), 288)
        self.assertFalse({'SALMONELLA', 'CAMPYLOBACTER'} & {t['pathogen'] for t in tasks})
        for pathogen, references in m.REFERENCES.items():
            origins = (2011, 2013, 2014) if pathogen == 'CRYPTOSPORIDIUM' else (2011, 2013, 2016)
            for temporal in references:
                for cutoff in origins:
                    arms = [t for t in tasks if (t['pathogen'], t['temporal'], t['cutoff']) == (pathogen, temporal, cutoff)]
                    self.assertEqual(len(arms), 12)
                    self.assertEqual({(t['local_seasonality'], t['weather'], t['weather_window'], t['age']) for t in arms},
                                     {(local, weather, window, age) for local in (False, True)
                                      for weather, window in ((False, 'current'), (True, 'current'), (True, 'lag01'))
                                      for age in (False, True)})
                    self.assertTrue(all(t['cutoff'] + 3 <= t['end_year'] for t in arms))
        self.assertEqual(len(m.base.matrix()), 72)
        self.assertGreater(min(t['seed'] for t in tasks), max(t['seed'] for t in m.base.matrix()) + 200000)

    def test_all_new_sampler_seeds_stay_inside_supported_range(self):
        tasks=m.matrix()
        self.assertEqual(tasks[0]['seed'],200000000)
        self.assertEqual(tasks[-1]['seed'],487000000)
        all_seeds=[]
        for task in tasks:
            self.assertTrue(1 <= task['seed'] <= 1000000000)
            # Exercise all four streams, every 100-draw batch and each RNG role.
            values=[task['seed']+stream*50000+start+offset
                    for stream in range(4)
                    for start in range(1,task['draws_per_stream']+1,100)
                    for offset in (0,10000,20000)]
            self.assertTrue(all(1 <= seed <= 1000000000 for seed in values))
            all_seeds.extend(values)
        self.assertEqual(len(all_seeds),len(set(all_seeds)))
        self.assertEqual(max(all_seeds),487170901)

    def test_legacy_seed_plan_remains_readonly_verifiable(self):
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)
            plan,_=self.fixture_plan(dest)
            plan.pop('seed_start')
            plan['tasks']=[dict(task=t) for t in m.matrix(900000000)]
            self.assertGreater(plan['tasks'][-1]['task']['seed'],1000000000)
            m.base.write(dest/'plan.json',plan)
            digest=m.base.sha(dest/'plan.json')
            before={str(p):p.read_bytes() for p in dest.rglob('*') if p.is_file()}
            m.verify(dest,plan,digest)
            self.assertEqual(before,{str(p):p.read_bytes() for p in dest.rglob('*') if p.is_file()})
            self.assertNotIn('seed_start',plan)

    def fixture_plan(self, dest):
        image = dest / 'runtime.sif'
        image.write_text('runtime')
        code = dest / 'bound.py'
        code.write_text('frozen')
        plan = dict(version=m.VERSION, seed_start=200000000, mode='historical_conditional', scientific_acceptance=False,
                    tasks=[dict(task=t) for t in m.matrix()], reused=[dict(task=t) for t in m.base.matrix()],
                    bindings={str(code): m.base.sha(code)}, container=str(image), container_sha256=m.base.sha(image),
                    container_stat=dict(size=image.stat().st_size, mtime_ns=image.stat().st_mtime_ns))
        m.base.write(dest / 'plan.json', plan)
        return plan, m.base.sha(dest / 'plan.json')

    def test_verify_rejects_changed_plan_matrix_sources_and_image(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d)
            p, digest = self.fixture_plan(dest)
            m.verify(dest, p, digest)
            (dest / 'bound.py').write_text('tampered')
            with self.assertRaises(ValueError): m.verify(dest, p, digest)
            (dest / 'bound.py').write_text('frozen')
            changed = copy.deepcopy(p)
            changed['tasks'][0]['task']['cutoff'] = 2016
            with self.assertRaisesRegex(ValueError, 'matrix'): m.verify(dest, changed, digest)
            (dest / 'plan.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'plan'): m.verify(dest, p, digest)
            m.base.write(dest / 'plan.json', p)
            (dest / 'runtime.sif').write_text('different-runtime')
            with self.assertRaisesRegex(ValueError, 'Runtime'): m.verify(dest, p, digest)

    def test_launch_immediately_submits_only_preparation(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for directory in ('scripts', 'docs', 'analysis_configs'):
                (root / directory).mkdir()
            for name in m.FILES:
                shutil.copyfile(repo / 'scripts' / name, root / 'scripts' / name)
            (root / 'docs/county_covariate_expansion_protocol.md').write_text('protocol')
            (root / 'analysis_configs/county_covariate_expansion_sources.json').write_text('{}')
            with patch.object(m.shutil, 'which', return_value='/bin/tool'), \
                 patch.object(m.base, 'submit', return_value='123') as submit, \
                 patch.object(m, 'prepare', side_effect=AssertionError('Heavy preparation on login host')):
                dest = m.launch(root)
            self.assertEqual(submit.call_count, 1)
            self.assertEqual(submit.call_args.args[1], 'foodnet_cov_prepare')
            self.assertFalse((dest / 'plan.json').exists())
            boot = m.base.read(dest / 'bootstrap.json')
            m.package_check(dest, boot)
            (dest / 'bundle/run_covariate_expansion.R').write_text('tampered')
            with self.assertRaises(ValueError): m.package_check(dest, boot)

    def test_output_manifest_rejects_traversal_tamper_and_missing_members(self):
        with tempfile.TemporaryDirectory() as d:
            work = Path(d)
            (work / 'report.csv').write_text('bound')
            outputs = {'report.csv': m.base.sha(work / 'report.csv')}
            m.safe_outputs(work, outputs, complete=True)
            for name in ('../outside', '/absolute', 'foo\\bar'):
                with self.assertRaises(ValueError): m.safe_outputs(work, {name: 'x'})
            (work / 'extra.csv').write_text('unbound')
            with self.assertRaisesRegex(ValueError, 'Incomplete'): m.safe_outputs(work, outputs, complete=True)
            (work / 'report.csv').write_text('tampered')
            with self.assertRaises(ValueError): m.safe_outputs(work, outputs)

    def test_existing_worker_output_is_never_overwritten_or_retried(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d)
            t = m.matrix()[0]
            t['output'] = str(dest / t['task_id'])
            work = Path(t['output']); work.mkdir(); (work / 'evidence.txt').write_text('keep')
            m.base.write(dest / 'plan.json', dict(tasks=[dict(task=t)]))
            with patch.object(m.subprocess, 'call') as call:
                with self.assertRaises(FileExistsError): m.worker(dest, 1, 'digest')
            call.assert_not_called()
            self.assertEqual((work / 'evidence.txt').read_text(), 'keep')

    def test_failed_pathogen_gate_stops_worker_before_fit(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d); t = m.matrix()[0]; t['output'] = str(dest / t['task_id'])
            taskfile = dest / 'task.json'; m.base.write(taskfile, t)
            entry = dict(task=t, task_json=str(taskfile), task_sha256=m.base.sha(taskfile), inputs={})
            m.base.write(dest / 'plan.json', dict(tasks=[entry]))
            m.base.write(dest / (t['pathogen'] + '_preflight_status.json'), dict(status='FAILED', plan_sha256='digest'))
            with patch.object(m, 'verify'), patch.object(m.subprocess, 'call') as call:
                self.assertEqual(m.worker(dest, 1, 'digest'), 1)
            call.assert_not_called()
            status = m.base.read(Path(t['output']) / 'task_status.json')
            self.assertEqual(status['status'], 'FAILED')
            self.assertIn('gate', status['reason'])

    def test_missing_workers_produce_failed_summary_and_archive(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / 'run'; dest.mkdir()
            t = m.matrix()[0]; t['output'] = str(dest / t['task_id'])
            image = dest / 'image.sif'; image.write_text('x')
            m.base.write(dest / 'plan.json', dict(tasks=[dict(task=t)], reused=[], validator='mock',
                                                container=str(image), container_sha256=m.base.sha(image)))
            with patch.object(m, 'verify'), patch.object(m, 'legacy', return_value=Mock()):
                self.assertEqual(m.collect(dest, 'digest'), 1)
            summary = m.base.read(dest / 'summary.json')
            self.assertEqual(summary['complete'], 0)
            self.assertFalse(summary['scientific_acceptance'])
            self.assertEqual(summary['expected'], 360)
            self.assertTrue(Path(str(dest) + '.tar.gz').is_file())

    def test_one_failed_worker_does_not_hide_other_completed_records(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / 'run'; dest.mkdir()
            image = dest / 'image.sif'; image.write_text('x')
            entries = []
            for i, t in enumerate(m.matrix()[:2]):
                work = dest / t['task_id']; work.mkdir(); (work / 'reports').mkdir()
                t['output'] = str(work)
                for name in ('stream_scores.csv', 'aggregate_tails.csv'):
                    (work / 'reports' / name).write_text('state,year,stream,mean_log_score\nCA,2012,0,-1\n')
                outputs = {str(p.relative_to(work)): m.base.sha(p) for p in work.rglob('*') if p.is_file()}
                taskfile = dest / (t['task_id'] + '.json'); m.base.write(taskfile, t)
                entries.append(dict(task=t, inputs={}, task_json=str(taskfile), task_sha256=m.base.sha(taskfile)))
                m.base.write(work / 'task_status.json', dict(task=t['task_id'], status='FAILED' if i == 0 else 'COMPLETE',
                    exit_status=1 if i == 0 else 0, plan_sha256='digest', reason='numerical failure', outputs=outputs, truth_sha256='truth'))
            m.base.write(dest / 'plan.json', dict(tasks=entries, reused=[], validator='mock', container=str(image), container_sha256=m.base.sha(image)))
            validator = Mock(); validator.validate.return_value = 'truth'
            with patch.object(m, 'verify'), patch.object(m, 'legacy', return_value=validator):
                self.assertEqual(m.collect(dest, 'digest'), 1)
            summary = m.base.read(dest / 'summary.json')
            self.assertEqual(summary['complete'], 1)
            self.assertEqual(summary['tasks'][0]['status'], 'FAILED_OR_MISSING')
            self.assertEqual(summary['tasks'][1]['status'], 'COMPLETE')

    def test_paired_truth_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / 'run'; dest.mkdir(); reused = []
            image = dest / 'image.sif'; image.write_text('x')
            for i, t in enumerate(m.base.matrix()[:2]):
                work = dest / t['task_id']; (work / 'reports').mkdir(parents=True)
                for name in ('stream_scores.csv', 'aggregate_tails.csv'):
                    (work / 'reports' / name).write_text('state,year,stream,mean_log_score\nCA,2012,0,-1\n')
                outputs = {str(p.relative_to(work)): m.base.sha(p) for p in work.rglob('*') if p.is_file()}
                reused.append(dict(task=t, work=str(work), outputs=outputs, truth_sha256='truth' + str(i)))
            m.base.write(dest / 'plan.json', dict(tasks=[], reused=reused, validator='mock', container=str(image), container_sha256=m.base.sha(image)))
            with patch.object(m, 'verify'), patch.object(m, 'legacy', return_value=Mock()):
                self.assertEqual(m.collect(dest, 'digest'), 1)
            summary = m.base.read(dest / 'summary.json')
            self.assertEqual(summary['complete'], 1)
            self.assertIn('Paired truth', summary['tasks'][1]['reason'])


    def score_block(self, temporal='rw1'):
        result = []
        for local in (False, True):
            for window, w in (('off', 0), ('current', 1), ('lag01', 2)):
                for age in (False, True):
                    result.append(dict(pathogen='YERSINIA', temporal=temporal, cutoff=2011,
                        state='CA', year=2012, stream=0, local_seasonality=local,
                        weather=window != 'off', weather_window='current' if window == 'off' else window,
                        age=age, mean_log_score=10*local + 3*w + 2*age + 4*age*w + 6*local*w + 7*local*age + 8*local*age*w))
        return result

    def test_factorial_contrasts_keep_temporals_separate_and_interactions_correct(self):
        result, missing = m.paired_contrasts(self.score_block() + self.score_block('ar1'))
        self.assertFalse(missing)
        self.assertEqual({r['temporal'] for r in result}, {'rw1', 'ar1'})
        for r in result:
            w = {'current': 1, 'lag01': 2}.get(r['weather_window'])
            if r['contrast'] == 'age_weather_difference_in_differences':
                self.assertEqual(r['log_score_difference'], (4 + 8*r['local_seasonality'])*w)
            if r['contrast'] == 'local_weather_difference_in_differences':
                self.assertEqual(r['log_score_difference'], (6 + 8*r['age'])*w)
            if r['contrast'] == 'local_on_minus_off':
                self.assertEqual(r['log_score_difference'], 10 + 6*(w or 0) + 7*r['age'] + 8*r['age']*(w or 0))
            if r['contrast'] == 'local_age_difference_in_differences':
                self.assertEqual(r['log_score_difference'], 7 + 8*(w or 0))
            if r['contrast'] == 'local_age_weather_three_way_difference':
                self.assertEqual(r['log_score_difference'], 8*w)

    def test_incomplete_contrast_block_not_filled_or_mixed_with_other_temporal(self):
        result, missing = m.paired_contrasts(self.score_block()[:-1] + self.score_block('ar1'))
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0]['temporal'], 'rw1')
        self.assertEqual(missing[0]['available_arms'], 11)
        self.assertTrue(result)
        self.assertEqual({r['temporal'] for r in result}, {'ar1'})

    def test_duplicate_contrast_arm_rejected(self):
        scores = self.score_block()
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            m.paired_contrasts(scores + [scores[0]])


if __name__ == '__main__':
    unittest.main()
