#!/usr/bin/env python3
"""Fit 54 spline arms and reuse the completed 108-cell monthly factorial."""
import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import launch_monthly_factorial as f

SOURCE = 'monthly_factorial_20260914_111339_242279'
FILES = tuple(sorted(set(f.FILES + ('launch_monthly_spline_factorial.py',
    'run_monthly_spline_factorial.R', 'monthly_spline_combination.R',
    'county_spline_candidate.R', 'prepare_monthly_spline_basis.R'))))


def matrix():
    return [dict(id=f.task_id(p,c,'spline',s),pathogen=p,cutoff=c,
                 temporal='spline',seasonal=s,end_year=2017 if p=='CRYPTOSPORIDIUM' else 2019,reused=False)
            for p in f.PATHOGENS for c in f.origins(p) for s in (False,True)]


def verify_basis(root):
    base=root/'analysis_configs/monthly_spline_basis'
    spec=json.loads((base/'manifest.json').read_text())
    if (spec['version'],spec['data_used'],spec['k'],spec['training_start'],spec['horizon_years']) != ('monthly_spline_basis_v1',False,6,2004,3):
        raise ValueError('Unexpected basis specification')
    if set(spec['files']) != {'2011.csv','2013.csv','2014.csv','2016.csv','generation_session.txt'}:
        raise ValueError('Incomplete prepared basis')
    expected={'scripts/prepare_monthly_spline_basis.R','scripts/monthly_spline_combination.R','scripts/county_spline_candidate.R'}
    if set(spec['sources'])!=expected:raise ValueError('Incomplete basis source binding')
    f.check_hashes({str(root/n):h for n,h in spec['sources'].items()})
    f.check_hashes({str(base/n):h for n,h in spec['files'].items()})
    return base


def control(base,plan,t):
    if t['reused']:
        ref=t['reference'];f.check_hashes(ref['inputs']);work=base/'references'/t['id']
        bound=dict(ref['inputs']);truth=ref['truth_sha256']
        for n in ('stream_scores.csv','aggregate_tails.csv','settings.csv'):
            path=str(work/n);bound[path]=plan['inputs'][path]
    else:
        work=base/t['id'];record=json.loads((work/'task_status.json').read_text())
        if record.get('status')!='COMPLETE' or record.get('exit_status')!=0 or record.get('task')!=t['id'] or record.get('plan_sha256')!=f.sha(base/'plan.json'):
            raise ValueError('Incomplete factorial control '+t['id'])
        truth=f.validate(work,t)
        if truth!=record.get('truth_sha256'):raise ValueError('Changed control truth')
        bound=f.bind_record(work,record);work=work/'result'
    f.check_hashes(bound)
    return dict(work=str(work),truth_sha256=truth,inputs=bound)


def prepare(root,dest,verified=True):
    root=Path(root).resolve();dest=Path(dest).resolve();basis=verify_basis(root)
    base=root/'output'/SOURCE;source=None;controls=[];provenance={}
    if verified:
        source=json.loads((base/'plan.json').read_text());f.verify(base,source,f.sha(base/'plan.json'),all_inputs=True)
        summary=json.loads((base/'summary.json').read_text())
        if summary['complete']!=108 or summary['expected']!=108 or summary['issues'] or len(summary['tasks'])!=108 or any(t['status']!='COMPLETE' for t in summary['tasks']):
            raise ValueError('The source factorial is incomplete or has issues')
        if {t['id'] for t in source['tasks']+source['references']}!={t['id'] for t in f.matrix()}:
            raise ValueError('Wrong source factorial domain')
        provenance={str(base/'plan.json'):f.sha(base/'plan.json'),str(base/'summary.json'):f.sha(base/'summary.json')}
        provenance.update(source['inputs']);provenance.update(source['provenance'])
        for t in source['references']+source['tasks']:
            ref=control(base,source,t);controls.append(dict(t,reference=ref,reused=True))
        for p in f.PATHOGENS:
            for c in f.origins(p):
                if len({t['reference']['truth_sha256'] for t in controls if (t['pathogen'],t['cutoff'])==(p,c)})!=1:
                    raise ValueError('Controls have different truth')
    dest.mkdir(parents=True,exist_ok=False);(dest/'scripts').mkdir();inputs={}
    for name in FILES:
        path=dest/'scripts'/name;shutil.copyfile(str(root/'scripts'/name),str(path));inputs[str(path)]=f.sha(path)
    shutil.copytree(str(basis),str(dest/'basis'))
    for path in (dest/'basis').iterdir():inputs[str(path)]=f.sha(path)
    doc=dest/'monthly_spline_factorial.md';shutil.copyfile(str(root/'docs/monthly_spline_factorial.md'),str(doc));inputs[str(doc)]=f.sha(doc)
    container=root/'foodnet-inla-fixed.sif'
    if verified:inputs[str(container)]=f.sha(container)
    for t in controls:
        target=dest/'references'/t['id'];target.mkdir(parents=True)
        for n in ('stream_scores.csv','aggregate_tails.csv','settings.csv'):
            path=target/n;shutil.copyfile(str(Path(t['reference']['work'])/n),str(path));inputs[str(path)]=f.sha(path)
    tasks=[]
    for i,t in enumerate(matrix()):
        candidate=audit='UNVERIFIED';runtime={}
        if verified:
            old=next(x for x in source['tasks'] if x['pathogen']==t['pathogen'] and x['cutoff']==t['cutoff'])
            j=next(j for j,x in enumerate(old['command']) if x.endswith('/run_monthly_factorial.R'))
            candidate,audit=old['command'][j+1:j+3];runtime=dict(old['inputs']);f.check_hashes(runtime)
            if candidate not in runtime or str(Path(audit)/'county_panel_INTERNAL.rds') not in runtime:raise ValueError('Unbound runtime source')
        t['seed']=600000000+i*1000000;t['inputs']=runtime
        t['command']=['singularity','exec','--cleanenv','--env','OPENBLAS_NUM_THREADS=1,OMP_NUM_THREADS=1,MKL_NUM_THREADS=1','--bind','/scicomp',str(container),'Rscript','--vanilla',str(dest/'scripts/run_monthly_spline_factorial.R'),candidate,audit,str(t['cutoff']),str(dest/t['id']/'result'),str(t['seed']),'TRUE' if t['seasonal'] else 'FALSE',str(t['end_year']),str(dest/'basis'/(str(t['cutoff'])+'.csv'))]
        tasks.append(t)
    plan=dict(version='monthly_spline_factorial_v1',verified=verified,inputs=inputs,provenance=provenance,tasks=tasks,references=controls,new_fits=54,reused_fits=108,total_cells=162,accepted=False,independent_validation=False,coverage_certified=False,cpo_ranking=False)
    (dest/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');digest=f.sha(dest/'plan.json');q=shlex.quote
    command='python3 '+q(str(dest/'scripts/launch_monthly_spline_factorial.py'))
    shell='#!/bin/bash\nset -euo pipefail\ncase "${SGE_TASK_ID:-undefined}" in\n'
    for i,t in enumerate(tasks,1):shell+=str(i)+') task='+t['id']+';;\n'
    shell+='*) exit 2;;\nesac\nexec '+command+' --worker '+q(str(dest))+' --task "$task" --digest '+digest+'\n'
    (dest/'run.sh').write_text(shell)
    (dest/'collect.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec '+command+' --collect '+q(str(dest))+' --digest '+digest+'\n')
    return plan


def verify(dest,plan,digest,task=None,all_inputs=False):
    if f.sha(dest/'plan.json')!=digest or plan.get('version')!='monthly_spline_factorial_v1' or not plan.get('verified'):raise ValueError('Changed or unverified spline plan')
    f.check_hashes(plan['inputs'])
    if task:f.check_hashes(task['inputs'])
    if all_inputs:
        f.check_hashes(plan['provenance'])
        for t in plan['tasks']:f.check_hashes(t['inputs'])
        for t in plan['references']:f.check_hashes(t['reference']['inputs'])


def validate(work,t):
    f.saved.validate_result(work,t);r=f.rows(work/'result/sensitivity_settings.csv')
    if len(r)!=1 or any(r[0].get(k)!=v for k,v in dict(temporal_model='spline',comparison='monthly_spline_factorial_v1',seasonal='TRUE' if t['seasonal'] else 'FALSE').items()) or int(r[0]['end_year'])!=t['end_year'] or float(r[0]['rate_center'])!=.0002 or int(r[0]['k'])!=6 or float(r[0]['slope_sd'])!=.5 or float(r[0]['nonlinear_sd_upper'])!=.5:raise ValueError('Spline specification differs')
    if not (work/'fit_INTERNAL.rds').is_file():raise ValueError('Missing spline checkpoint')
    if re.search(r'vb[.]correction[^\n]*aborted',(work/'task.log').read_text(errors='replace'),re.I):raise ValueError('Aborted approximation')
    return f.truth_identity(work/'heldout_truth_INTERNAL.csv',t['cutoff'])


def worker(dest,name,digest):
    dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());t=next(t for t in plan['tasks'] if t['id']==name);work=dest/name;work.mkdir(exist_ok=False)
    record=dict(task=name,status='FAILED',exit_status=1,plan_sha256=digest)
    try:
        verify(dest,plan,digest,t)
        with (work/'task.log').open('w') as log:code=subprocess.call(t['command'],stdout=log,stderr=subprocess.STDOUT)
        if code:raise ValueError('R exit '+str(code))
        truth=validate(work,t);expected={r['reference']['truth_sha256'] for r in plan['references'] if (r['pathogen'],r['cutoff'])==(t['pathogen'],t['cutoff'])}
        if expected!={truth}:raise ValueError('Spline and control truth differ')
        verify(dest,plan,digest,t)
        record.update(status='COMPLETE',exit_status=0,truth_sha256=truth,outputs={str(p.relative_to(work)):f.sha(p) for p in work.rglob('*') if p.is_file()})
    except (OSError,ValueError,KeyError,StopIteration) as e:record['reason']=str(e)
    (work/'task_status.json').write_text(json.dumps(record,indent=2)+'\n');return record['exit_status']


def contrasts(scores):
    result=[];equal=[]
    for reference in ('rw1','ar1'):
        # The existing four-arm algebra is unchanged; relabel only at its boundary.
        selected=[dict(r,temporal='rw1' if r['temporal']==reference else 'ar1') for r in scores if r['temporal'] in (reference,'spline')]
        site,avg=f.contrasts(selected)
        for source,target in ((site,result),(avg,equal)):
            for r in source:
                z={k:v for k,v in r.items() if k not in ('ar1_minus_rw1_nonseasonal','ar1_minus_rw1_seasonal','seasonality_under_rw1','seasonality_under_ar1')}
                z.update(reference=reference,spline_minus_reference_nonseasonal=r['ar1_minus_rw1_nonseasonal'],spline_minus_reference_seasonal=r['ar1_minus_rw1_seasonal'],seasonality_under_reference=r['seasonality_under_rw1'],seasonality_under_spline=r['seasonality_under_ar1']);target.append(z)
    return result,equal


def collect(dest,digest):
    dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());issues=[];summary=[];scores=[];tails=[];truths={}
    try:verify(dest,plan,digest,all_inputs=True)
    except (OSError,ValueError,KeyError) as e:issues.append(str(e))
    for t in plan['references']+plan['tasks']:
        try:
            if t['reused']:
                f.check_hashes(t['reference']['inputs']);out=dest/'references'/t['id'];truth=t['reference']['truth_sha256']
                f.check_hashes({str(out/n):plan['inputs'][str(out/n)] for n in ('stream_scores.csv','aggregate_tails.csv','settings.csv')})
            else:
                work=dest/t['id'];record=json.loads((work/'task_status.json').read_text())
                if record.get('status')!='COMPLETE' or record.get('task')!=t['id'] or record.get('plan_sha256')!=digest or record.get('exit_status')!=0:raise ValueError(record.get('reason','Incomplete task'))
                truth=validate(work,t);f.bind_record(work,record);out=work/'result'
                if truth!=record.get('truth_sha256'):raise ValueError('Changed truth identity')
            truths.setdefault((t['pathogen'],t['cutoff']),set()).add(truth)
            for n,target in (('stream_scores.csv',scores),('aggregate_tails.csv',tails)):
                target.extend(dict(task=t['id'],pathogen=t['pathogen'],cutoff=t['cutoff'],temporal=t['temporal'],seasonal=t['seasonal'],reused=t['reused'],**r) for r in f.rows(out/n))
            summary.append(dict(task=t['id'],status='COMPLETE',reused=t['reused']))
        except (OSError,ValueError,KeyError) as e:summary.append(dict(task=t['id'],status='FAILED_OR_MISSING',reason=str(e),reused=t['reused']))
    if any(len(v)!=1 for v in truths.values()):issues.append('Inconsistent paired truth')
    site,equal=([],[]) if issues else contrasts(scores)
    for name,data in (('all_stream_scores.csv',scores),('all_aggregate_tails.csv',tails),('spline_site_contrasts.csv',site),('spline_equal_site_contrasts.csv',equal)):
        path=dest/name
        if path.exists():path.unlink()
        if data:
            with path.open('w',newline='') as handle:w=csv.DictWriter(handle,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    complete=sum(r['status']=='COMPLETE' for r in summary)
    result=dict(tasks=summary,issues=issues,complete=complete,expected=162,new_fits=54,reused_fits=108,accepted=False,independent_validation=False,cpo_ranking=False)
    (dest/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    files=[p for p in dest.rglob('*') if p.is_file() and not p.is_symlink() and p.suffix.lower() in ('.csv','.json','.txt','.log','.py','.r','.sh','.md') and '_INTERNAL' not in p.name and p.name!='report_sha256.json']
    (dest/'report_sha256.json').write_text(json.dumps({str(p.relative_to(dest)):f.sha(p) for p in files},indent=2)+'\n')
    with tarfile.open(str(dest)+'.tar.gz','w:gz') as archive:
        for path in files+[dest/'report_sha256.json']:archive.add(str(path),arcname=str(path.relative_to(dest)))
    print(json.dumps(result,indent=2));print('Archive: '+str(dest)+'.tar.gz');return 0 if complete==162 and not issues else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare-only',action='store_true');parser.add_argument('--worker');parser.add_argument('--task');parser.add_argument('--collect');parser.add_argument('--digest');args=parser.parse_args()
    if args.worker or args.collect:
        if not args.digest or (args.worker and not args.task):parser.error('Missing task identity')
        return worker(args.worker,args.task,args.digest) if args.worker else collect(args.collect,args.digest)
    root=Path(__file__).resolve().parents[1];dest=root/'output'/('monthly_spline_factorial_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    if not args.prepare_only and any(not shutil.which(t) for t in ('qsub','singularity')):parser.error('Load singularity and run on SGE host')
    try:prepare(root,dest,not args.prepare_only)
    except (OSError,ValueError,KeyError,StopIteration) as e:parser.error(str(e))
    print('Output: '+str(dest),flush=True)
    if args.prepare_only:return 0
    base=['qsub','-terse','-V','-cwd','-S','/bin/bash','-j','y'];ledger={}
    def submit(name,script,slots,time,rss,vmem,array=None,hold=None):
        cmd=base+['-N',name,'-pe','smp',str(slots),'-l','h_rt=%s,h_rss=%sM,mem_free=%sM,h_vmem=%sG'%(time,rss,rss,vmem),'-o',str(dest)]
        if array:cmd+=['-t',array]
        if hold:cmd+=['-hold_jid',hold]
        job=subprocess.check_output(cmd+[str(dest/script)],universal_newlines=True).strip();ledger[name]=job;(dest/'submission.json').write_text(json.dumps(ledger,indent=2)+'\n');print(name+': '+job,flush=True)
        match=re.match(r'^(\d+)(?:[.\s]|$)',job)
        if not match:raise ValueError('Unexpected submission response; inspect queue before retry')
        return match.group(1)
    fits=submit('foodnet_monthly_spline','run.sh',4,'48:00:00',53248,68,'1-54')
    submit('foodnet_spline_collect','collect.sh',1,'04:00:00',8192,16,hold=fits)
    print('54 new fits; 108 reused controls. Final log: '+str(dest)+'; archive: '+str(dest)+'.tar.gz');return 0


if __name__=='__main__':sys.exit(main())
