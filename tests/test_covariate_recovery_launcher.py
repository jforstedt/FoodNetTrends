import collections
import copy
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import launch_covariate_recovery as m

ARCHIVE=Path('/mnt/c/Users/User/Downloads/county_covariate_expansion_20260916_114512_840990.tar.gz')

class RecoveryTests(unittest.TestCase):
    def test_seed_scope_and_sampler_offsets(self):
        seeds=[m.seed(i) for i in range(187)]
        self.assertEqual((min(seeds),max(seeds)),(600000000,786000000))
        all_seeds=[s+k*50000+start+offset for s in seeds for k in range(4) for start in range(1,1001,100) for offset in (0,10000,20000)]
        self.assertEqual(len(all_seeds),len(set(all_seeds)))
        self.assertLessEqual(max(all_seeds),1000000000)
        for i in (-1,187):
            with self.assertRaises(ValueError):m.seed(i)

    def test_only_known_numerical_case_refits(self):
        t={'task_id':m.NUMERICAL,'seed':1100000000}
        log='vb.correction: aborted\nLocal seasonal fit failed numerical gate'
        self.assertEqual(m.classify(t,log),'refit_once_single_thread')
        for badlog in ('Invalid sampling settings','vb.correction: aborted','Local seasonal fit failed numerical gate'):
            with self.assertRaises(ValueError):m.classify(t,badlog)
        t['task_id']='OTHER'
        with self.assertRaises(ValueError):m.classify(t,log+'\nInvalid sampling settings')
        self.assertEqual(m.classify(t,'Error: Invalid sampling settings'),'saved_fit_rescore')
        t['seed']=1000000000
        with self.assertRaises(ValueError):m.classify(t,'Invalid sampling settings')

    @unittest.skipUnless(ARCHIVE.is_file(),'Local completed archive not present')
    def test_real_archive_has_186_rescores_one_retry_173_preserved(self):
        with tarfile.open(ARCHIVE) as archive:
            plan=json.load(archive.extractfile('plan.json')); summary=json.load(archive.extractfile('summary.json'))
            status={r['task']:r['status'] for r in summary['tasks']}
            modes=[]; preserved=0
            for entry in plan['tasks']:
                t=entry['task']
                if status[t['task_id']]=='COMPLETE':preserved+=1;continue
                log=archive.extractfile(t['task_id']+'/task.log').read().decode(errors='replace')
                modes.append(m.classify(t,log))
            preserved+=len(plan['reused'])
            self.assertEqual(preserved,173)
            self.assertEqual(collections.Counter(modes),{'saved_fit_rescore':186,'refit_once_single_thread':1})

    def fixture(self,dest):
        image=dest/'image.sif';image.write_text('image')
        code=dest/'source.py';code.write_text('bound')
        tasklist=[]
        for i in range(187):
            t={'task_id':m.NUMERICAL if i==186 else 'task'+str(i),'seed':m.seed(i)}
            tasklist.append(dict(task=t,mode='refit_once_single_thread' if i==186 else 'saved_fit_rescore'))
        plan=dict(version=m.VERSION,scientific_acceptance=False,tasks=tasklist,references=[{} for _ in range(173)],
                  bindings={str(code):m.base.sha(code)},container=str(image),container_stat=dict(size=image.stat().st_size,mtime_ns=image.stat().st_mtime_ns))
        m.base.write(dest/'plan.json',plan)
        return plan,m.base.sha(dest/'plan.json')

    def test_plan_hash_bindings_modes_and_runtime_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp);plan,digest=self.fixture(dest);m.verify(dest,plan,digest)
            with self.assertRaises(ValueError):m.verify(dest,plan,'wrong')
            bad=copy.deepcopy(plan);bad['tasks'][-1]['task']['task_id']='OTHER'
            with self.assertRaisesRegex(ValueError,'refit'):m.verify(dest,bad,digest)
            bad=copy.deepcopy(plan);bad['tasks'][0]['task']['seed']=1000000001
            with self.assertRaisesRegex(ValueError,'seed'):m.verify(dest,bad,digest)
            (dest/'source.py').write_text('changed')
            with self.assertRaises(ValueError):m.verify(dest,plan,digest)
            (dest/'source.py').write_text('bound');(dest/'image.sif').write_text('different')
            with self.assertRaisesRegex(ValueError,'Runtime'):m.verify(dest,plan,digest)

    def test_worker_never_overwrites_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp);work=dest/'existing';work.mkdir();(work/'keep').write_text('preserve')
            m.base.write(dest/'plan.json',dict(tasks=[dict(task=dict(output=str(work)))]))
            with patch.object(m.subprocess,'call') as call:
                with self.assertRaises(FileExistsError):m.worker(dest,1,'digest')
            call.assert_not_called();self.assertEqual((work/'keep').read_text(),'preserve')

    def test_worker_dispatches_rescore_without_fit_script_and_checks_inputs(self):
        for mode,script in [('saved_fit_rescore','rescore_covariate_expansion.R'),('refit_once_single_thread','run_covariate_expansion.R')]:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                dest=Path(tmp);taskfile=dest/'task.json';taskfile.write_text('{}')
                checkpoint=dest/'saved.rds';checkpoint.write_text('frozen checkpoint')
                e=dict(task=dict(task_id='task',output=str(dest/'result')),mode=mode,inputs={str(checkpoint):m.base.sha(checkpoint)},task_json=str(taskfile),task_sha256=m.base.sha(taskfile))
                m.base.write(dest/'plan.json',dict(tasks=[e],container='runtime'))
                with patch.object(m,'verify'),patch.object(m,'validate',return_value='truth'),patch.object(m.base,'runtime_command',return_value=['stub']) as command,patch.object(m.subprocess,'call',return_value=0) as call:
                    self.assertEqual(m.worker(dest,1,'digest'),0)
                self.assertEqual(command.call_args.args[1],dest/'bundle'/script)
                self.assertEqual(call.call_count,1)
                self.assertEqual(checkpoint.read_text(),'frozen checkpoint')
                e['task']['output']=str(dest/'badresult');checkpoint.write_text('modified')
                m.base.write(dest/'plan.json',dict(tasks=[e],container='runtime'))
                with patch.object(m,'verify'),patch.object(m.subprocess,'call') as call:
                    self.assertEqual(m.worker(dest,1,'digest'),1)
                call.assert_not_called()

    def test_launch_submits_preparation_immediately_without_heavy_prepare(self):
        repo=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('scripts','docs','analysis_configs'):(root/name).mkdir()
            for name in m.FILES:shutil.copyfile(repo/'scripts'/name,root/'scripts'/name)
            (root/'analysis_configs/covariate_expansion_recovery_source.json').write_text('{}')
            (root/'docs/covariate_expansion_recovery.md').write_text('protocol')
            with patch.object(m.shutil,'which',return_value='/bin/tool'),patch.object(m.base,'submit',return_value='123') as submit,patch.object(m,'prepare',side_effect=AssertionError('heavy login work')):
                m.launch(root)
            self.assertEqual(submit.call_count,1)
            dest=next((root/'output').iterdir())
            self.assertFalse((dest/'plan.json').exists())
            self.assertEqual(m.base.read(dest/'preparation_submission.json')['job'],'123')

    def test_collect_partial_failure_preserves_completed_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'run';dest.mkdir();image=dest/'runtime.sif';image.write_text('runtime')
            t=dict(m.expansion.matrix()[0]);t['output']=str(dest/'failed')
            good=dict(m.expansion.matrix()[1]);work=dest/'reference';(work/'reports').mkdir(parents=True)
            for name in ('stream_scores.csv','aggregate_tails.csv'):
                (work/'reports'/name).write_text('state,year,stream,mean_log_score\nCA,2012,0,-1\n')
            outputs={str(p.relative_to(work)):m.base.sha(p) for p in work.rglob('*') if p.is_file()}
            m.base.write(dest/'plan.json',dict(tasks=[dict(task=t,mode='saved_fit_rescore')],references=[dict(task=good,work=str(work),outputs=outputs,truth_sha256='truth')],container=str(image),container_sha256=m.base.sha(image)))
            with patch.object(m,'verify'):
                self.assertEqual(m.collect(dest,'digest'),1)
            summary=m.base.read(dest/'summary.json')
            self.assertEqual(summary['complete'],1)
            self.assertEqual([r['status'] for r in summary['tasks']],['FAILED_OR_MISSING','COMPLETE'])
            self.assertTrue(Path(str(dest)+'.tar.gz').is_file())
            for name,h in outputs.items():self.assertEqual(m.base.sha(work/name),h)

    def test_reference_copy_and_preparation_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';source.mkdir();target=root/'existing';target.mkdir()
            (target/'evidence.txt').write_text('preserve')
            with self.assertRaisesRegex(ValueError,'existing reference'):m.copy_reports(source,target,{})
            self.assertEqual((target/'evidence.txt').read_text(),'preserve')
            for sentinel in ('plan.json','submission.json'):
                dest=root/sentinel.replace('.json','');dest.mkdir();(dest/sentinel).write_text('keep')
                with patch.object(m.base,'check') as check,patch.object(m.base,'submit') as submit:
                    with self.assertRaisesRegex(ValueError,'prepared recovery'):m.prepare(dest,'digest')
                check.assert_not_called();submit.assert_not_called()
                self.assertEqual((dest/sentinel).read_text(),'keep')

    def test_report_copy_rejects_wrong_hash_and_excludes_private_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'source';dst=Path(tmp)/'dest';(src/'reports').mkdir(parents=True)
            (src/'reports/public.csv').write_text('public');(src/'reports/private_INTERNAL.csv').write_text('private')
            with self.assertRaises(ValueError):m.copy_reports(src,dst,{'reports/public.csv':'wrong'})
            out=m.copy_reports(src,dst,{'reports/public.csv':m.base.sha(src/'reports/public.csv'),'reports/private_INTERNAL.csv':m.base.sha(src/'reports/private_INTERNAL.csv')})
            self.assertEqual(set(out),{'reports/public.csv'})
            self.assertFalse((dst/'reports/private_INTERNAL.csv').exists())

if __name__=='__main__':unittest.main()
