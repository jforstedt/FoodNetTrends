#!/usr/bin/env python3
"""Add the 162 spatial arms to the completed 162 IID temporal/seasonal controls."""
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
import launch_monthly_spline_factorial as s

SOURCE='monthly_spline_factorial_20260914_120120_695932'
FILES=tuple(sorted(set(s.FILES+('launch_monthly_spatial_factorial.py','run_monthly_spatial_factorial.R','monthly_spatial_combination.R'))))


def matrix():
    return [dict(id=s.f.task_id(p,c,m,season)+'_bym2',pathogen=p,cutoff=c,temporal=m,seasonal=season,spatial='bym2',reused=False,end_year=2017 if p=='CRYPTOSPORIDIUM' else 2019) for p in s.f.PATHOGENS for c in s.f.origins(p) for m in ('rw1','ar1','spline') for season in (False,True)]


def load_control(base,plan,t):
    if t['reused']:
        bound=dict(t['reference']['inputs']);out=base/'references'/t['id'];truth=t['reference']['truth_sha256']
        for n in ('stream_scores.csv','aggregate_tails.csv','settings.csv'):bound[str(out/n)]=plan['inputs'][str(out/n)]
    else:
        work=base/t['id'];record=json.loads((work/'task_status.json').read_text())
        if record.get('status')!='COMPLETE' or record.get('task')!=t['id'] or record.get('exit_status')!=0 or record.get('plan_sha256')!=s.f.sha(base/'plan.json'):raise ValueError('Incomplete source spline control')
        truth=s.validate(work,t)
        if truth!=record.get('truth_sha256'):raise ValueError('Changed source truth')
        bound=s.f.bind_record(work,record);out=work/'result'
    s.f.check_hashes(bound)
    return dict(work=str(out),inputs=bound,truth_sha256=truth)


def prepare(root,dest,verified=True):
    root=Path(root).resolve();dest=Path(dest).resolve();basis=s.verify_basis(root);base=root/'output'/SOURCE
    old=None;references=[];provenance={}
    if verified:
        old=json.loads((base/'plan.json').read_text());s.verify(base,old,s.f.sha(base/'plan.json'),all_inputs=True)
        summary=json.loads((base/'summary.json').read_text())
        expected={s.f.task_id(t['pathogen'],t['cutoff'],t['temporal'],t['seasonal']) for t in matrix()}
        if len(old['tasks']+old['references'])!=162 or {t['id'] for t in old['tasks']+old['references']}!=expected or summary['complete']!=162 or summary['issues']:raise ValueError('Source spline factorial is not complete and consistent')
        provenance=dict(old['provenance']);provenance.update(old['inputs']);provenance[str(base/'plan.json')]=s.f.sha(base/'plan.json');provenance[str(base/'summary.json')]=s.f.sha(base/'summary.json')
        for t in old['references']+old['tasks']:references.append(dict(t,reused=True,spatial='iid',reference=load_control(base,old,t)))
        for p in s.f.PATHOGENS:
            for c in s.f.origins(p):
                if len({r['reference']['truth_sha256'] for r in references if (r['pathogen'],r['cutoff'])==(p,c)})!=1:raise ValueError('Controls have differing truth')
    dest.mkdir(parents=True,exist_ok=False);(dest/'scripts').mkdir();inputs={}
    for name in FILES:
        path=dest/'scripts'/name;shutil.copyfile(str(root/'scripts'/name),str(path));inputs[str(path)]=s.f.sha(path)
    shutil.copytree(str(basis),str(dest/'basis'));(dest/'graph').mkdir()
    for name in ('counties.csv','edges.csv','provenance.json'):shutil.copyfile(str(root/'analysis_configs/county_pilot'/name),str(dest/'graph'/name))
    for folder in ('basis','graph'):
        for path in (dest/folder).iterdir():inputs[str(path)]=s.f.sha(path)
    for name in ('monthly_spatial_combination.md','broader_combination_batch.md'):
        path=dest/name;shutil.copyfile(str(root/'docs'/name),str(path));inputs[str(path)]=s.f.sha(path)
    container=root/'foodnet-inla-fixed.sif'
    if verified:inputs[str(container)]=s.f.sha(container)
    for t in references:
        target=dest/'references'/t['id'];target.mkdir(parents=True)
        for name in ('stream_scores.csv','aggregate_tails.csv','settings.csv'):
            path=target/name;shutil.copyfile(str(Path(t['reference']['work'])/name),str(path));inputs[str(path)]=s.f.sha(path)
    tasks=[]
    for i,t in enumerate(matrix()):
        candidate=audit='UNVERIFIED';runtime={}
        if verified:
            original=next(x for x in old['tasks'] if (x['pathogen'],x['cutoff'])==(t['pathogen'],t['cutoff']))
            j=next(j for j,x in enumerate(original['command']) if x.endswith('/run_monthly_spline_factorial.R'))
            candidate,audit=original['command'][j+1:j+3];runtime=dict(original['inputs']);s.f.check_hashes(runtime)
            if candidate not in runtime or str(Path(audit)/'county_panel_INTERNAL.rds') not in runtime:raise ValueError('Unbound runtime data')
        t.update(seed=800000000+i*1000000,inputs=runtime)
        t['command']=['singularity','exec','--cleanenv','--env','OPENBLAS_NUM_THREADS=1,OMP_NUM_THREADS=1,MKL_NUM_THREADS=1','--bind','/scicomp',str(container),'Rscript','--vanilla',str(dest/'scripts/run_monthly_spatial_factorial.R'),candidate,audit,str(t['cutoff']),str(dest/t['id']/'result'),str(t['seed']),t['temporal'],'TRUE' if t['seasonal'] else 'FALSE',str(t['end_year']),str(dest/'basis'/(str(t['cutoff'])+'.csv')),str(dest/'graph/counties.csv'),str(dest/'graph/edges.csv')]
        tasks.append(t)
    plan=dict(version='monthly_spatial_factorial_v1',verified=verified,inputs=inputs,provenance=provenance,tasks=tasks,references=references,new_fits=162,reused_fits=162,total_cells=324,accepted=False,coverage_certified=False,independent_validation=False,cpo_ranking=False)
    (dest/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');digest=s.f.sha(dest/'plan.json');q=shlex.quote;cmd='python3 '+q(str(dest/'scripts/launch_monthly_spatial_factorial.py'))
    shell='#!/bin/bash\nset -euo pipefail\ncase "${SGE_TASK_ID:-undefined}" in\n'
    for i,t in enumerate(tasks,1):shell+=str(i)+') task='+t['id']+';;\n'
    shell+='*) exit 2;;\nesac\nexec '+cmd+' --worker '+q(str(dest))+' --task "$task" --digest '+digest+'\n'
    (dest/'run.sh').write_text(shell);(dest/'collect.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec '+cmd+' --collect '+q(str(dest))+' --digest '+digest+'\n');return plan


def verify(dest,plan,digest,t=None,all_inputs=False):
    if s.f.sha(dest/'plan.json')!=digest or plan.get('version')!='monthly_spatial_factorial_v1' or not plan.get('verified'):raise ValueError('Unverified or changed spatial plan')
    s.f.check_hashes(plan['inputs'])
    if t:s.f.check_hashes(t['inputs'])
    if all_inputs:
        s.f.check_hashes(plan['provenance'])
        for task in plan['tasks']:s.f.check_hashes(task['inputs'])
        for ref in plan['references']:s.f.check_hashes(ref['reference']['inputs'])


def validate(work,t):
    s.f.saved.validate_result(work,t);rows=s.f.rows(work/'result/sensitivity_settings.csv')
    if len(rows)!=1:raise ValueError('Missing spatial settings')
    r=rows[0]
    for k,v in dict(comparison='monthly_spatial_factorial_v1',spatial='bym2',temporal_model=t['temporal'],seasonal='TRUE' if t['seasonal'] else 'FALSE').items():
        if r.get(k)!=v:raise ValueError('Spatial model identity differs')
    for k,v in dict(end_year=t['end_year'],rate_center=.0002,sd_upper=1,sd_tail=.01,phi_u=.5,phi_probability=.5,n_counties=486,n_components=10,n_edges=1210).items():
        if float(r[k])!=v:raise ValueError('Spatial prior/graph differs: '+k)
    if not (work/'fit_INTERNAL.rds').is_file():raise ValueError('Missing checkpoint')
    if re.search(r'vb[.]correction[^\n]*aborted',(work/'task.log').read_text(errors='replace'),re.I):raise ValueError('Aborted approximation')
    return s.f.truth_identity(work/'heldout_truth_INTERNAL.csv',t['cutoff'])


def worker(dest,name,digest):
    dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());t=next(t for t in plan['tasks'] if t['id']==name);work=dest/name;work.mkdir(exist_ok=False)
    record=dict(task=name,status='FAILED',exit_status=1,plan_sha256=digest)
    try:
        verify(dest,plan,digest,t)
        with (work/'task.log').open('w') as log:code=subprocess.call(t['command'],stdout=log,stderr=subprocess.STDOUT)
        if code:raise ValueError('R exit '+str(code))
        truth=validate(work,t)
        if {r['reference']['truth_sha256'] for r in plan['references'] if (r['pathogen'],r['cutoff'])==(t['pathogen'],t['cutoff'])}!={truth}:raise ValueError('Spatial and IID truth differ')
        verify(dest,plan,digest,t);record.update(status='COMPLETE',exit_status=0,truth_sha256=truth,outputs={str(p.relative_to(work)):s.f.sha(p) for p in work.rglob('*') if p.is_file()})
    except (OSError,ValueError,KeyError) as e:record['reason']=str(e)
    (work/'task_status.json').write_text(json.dumps(record,indent=2)+'\n');return record['exit_status']


def contrasts(scores):
    index={};spatial=[];temporal=[]
    for r in scores:
        key=(r['pathogen'],int(r['cutoff']),r['state'],int(r['year']),int(r['stream']),r['temporal'],r['seasonal'],r['spatial'])
        if key in index:raise ValueError('Duplicate spatial score cell')
        index[key]=float(r['mean_log_score'])
    for k in sorted({x[:-1] for x in index}):
        if k+('iid',) in index and k+('bym2',) in index:spatial.append(dict(pathogen=k[0],cutoff=k[1],state=k[2],year=k[3],stream=k[4],temporal=k[5],seasonal=k[6],bym2_minus_iid=index[k+('bym2',)]-index[k+('iid',)]))
    for mode in ('iid','bym2'):
        site,_=s.contrasts([r for r in scores if r['spatial']==mode]);temporal.extend(dict(r,spatial=mode) for r in site)
    ix={(r['pathogen'],r['cutoff'],r['state'],r['year'],r['stream'],r['reference'],r['spatial']):r for r in temporal};three=[]
    for k in sorted({x[:-1] for x in ix}):
        if k+('iid',) in ix and k+('bym2',) in ix:three.append(dict(pathogen=k[0],cutoff=k[1],state=k[2],year=k[3],stream=k[4],reference=k[5],spatial_temporal_seasonal_interaction=ix[k+('bym2',)]['interaction']-ix[k+('iid',)]['interaction']))
    return spatial,temporal,three


def ar1_rw1_contrasts(scores):
    """Direct AR1/RW1 temporal-seasonal contrasts under each county prior."""
    temporal=[]
    for mode in ('iid','bym2'):
        selected=[r for r in scores if r['spatial']==mode and r['temporal'] in ('rw1','ar1')]
        site,_=s.f.contrasts(selected)
        temporal.extend(dict(r,spatial=mode) for r in site)
    ix={(r['pathogen'],r['cutoff'],r['state'],r['year'],r['stream'],r['spatial']):r for r in temporal}
    three=[]
    for k in sorted({x[:-1] for x in ix}):
        if k+('iid',) in ix and k+('bym2',) in ix:
            three.append(dict(pathogen=k[0],cutoff=k[1],state=k[2],year=k[3],stream=k[4],
                spatial_ar1_rw1_seasonal_interaction=ix[k+('bym2',)]['interaction']-ix[k+('iid',)]['interaction']))
    return temporal,three


def equal_sites(rows,metrics):
    grouped={}
    for r in rows:
        key=tuple((k,v) for k,v in r.items() if k not in ('state',)+tuple(metrics));grouped.setdefault(key,[]).append(r)
    return [dict(key,sites=10,**{m:sum(r[m] for r in rs)/10 for m in metrics}) for key,rs in grouped.items() if len(rs)==10 and {r['state'] for r in rs}==set(s.f.STATES)]


def collect(dest,digest):
    dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());issues=[];summary=[];scores=[];tails=[];truths={}
    try:verify(dest,plan,digest,all_inputs=True)
    except (OSError,ValueError,KeyError) as e:issues.append(str(e))
    for t in plan['references']+plan['tasks']:
        try:
            if t['reused']:
                s.f.check_hashes(t['reference']['inputs']);out=dest/'references'/t['id'];truth=t['reference']['truth_sha256']
                s.f.check_hashes({str(out/n):plan['inputs'][str(out/n)] for n in ('stream_scores.csv','aggregate_tails.csv','settings.csv')})
            else:
                work=dest/t['id'];r=json.loads((work/'task_status.json').read_text())
                if r.get('status')!='COMPLETE' or r.get('task')!=t['id'] or r.get('plan_sha256')!=digest or r.get('exit_status')!=0:raise ValueError(r.get('reason','Incomplete task'))
                truth=validate(work,t);s.f.bind_record(work,r);out=work/'result'
                if truth!=r.get('truth_sha256'):raise ValueError('Changed task truth')
            truths.setdefault((t['pathogen'],t['cutoff']),set()).add(truth)
            for name,target in (('stream_scores.csv',scores),('aggregate_tails.csv',tails)):target.extend(dict(task=t['id'],pathogen=t['pathogen'],cutoff=t['cutoff'],temporal=t['temporal'],seasonal=t['seasonal'],spatial=t['spatial'],reused=t['reused'],**r) for r in s.f.rows(out/name))
            summary.append(dict(task=t['id'],status='COMPLETE',reused=t['reused']))
        except (OSError,ValueError,KeyError) as e:summary.append(dict(task=t['id'],status='FAILED_OR_MISSING',reason=str(e),reused=t['reused']))
    if any(len(v)!=1 for v in truths.values()):issues.append('Inconsistent paired truth')
    spatial,temporal,three=([],[],[]) if issues else contrasts(scores)
    direct,direct_three=([],[]) if issues else ar1_rw1_contrasts(scores)
    products=[('all_stream_scores.csv',scores),('all_aggregate_tails.csv',tails)]
    for name,data,metrics in [('spatial',spatial,('bym2_minus_iid',)),('temporal_seasonal',temporal,('spline_minus_reference_nonseasonal','spline_minus_reference_seasonal','seasonality_under_reference','seasonality_under_spline','interaction')),('three_way',three,('spatial_temporal_seasonal_interaction',)),('ar1_rw1_temporal_seasonal',direct,('ar1_minus_rw1_nonseasonal','ar1_minus_rw1_seasonal','seasonality_under_rw1','seasonality_under_ar1','interaction')),('ar1_rw1_three_way',direct_three,('spatial_ar1_rw1_seasonal_interaction',))]:products.extend([(name+'_site_contrasts.csv',data),(name+'_equal_site_contrasts.csv',equal_sites(data,metrics))])
    for name,data in products:
        path=dest/name
        if path.exists():path.unlink()
        if data:
            with path.open('w',newline='') as h:w=csv.DictWriter(h,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    complete=sum(r['status']=='COMPLETE' for r in summary);result=dict(tasks=summary,issues=issues,complete=complete,expected=324,new_fits=162,reused_fits=162,accepted=False,independent_validation=False,cpo_ranking=False)
    (dest/'summary.json').write_text(json.dumps(result,indent=2)+'\n');files=[p for p in dest.rglob('*') if p.is_file() and not p.is_symlink() and p.suffix.lower() in ('.csv','.json','.txt','.log','.py','.r','.sh','.md') and '_INTERNAL' not in p.name and p.name!='report_sha256.json']
    (dest/'report_sha256.json').write_text(json.dumps({str(p.relative_to(dest)):s.f.sha(p) for p in files},indent=2)+'\n')
    with tarfile.open(str(dest)+'.tar.gz','w:gz') as tar:
        for p in files+[dest/'report_sha256.json']:tar.add(str(p),arcname=str(p.relative_to(dest)))
    print(json.dumps(result,indent=2));print('Archive: '+str(dest)+'.tar.gz');return 0 if complete==324 and not issues else 1


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare-only',action='store_true');p.add_argument('--worker');p.add_argument('--collect');p.add_argument('--task');p.add_argument('--digest');a=p.parse_args()
    if a.worker or a.collect:
        if not a.digest or (a.worker and not a.task):p.error('Missing task identity')
        return worker(a.worker,a.task,a.digest) if a.worker else collect(a.collect,a.digest)
    root=Path(__file__).resolve().parents[1];dest=root/'output'/('monthly_spatial_factorial_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    if not a.prepare_only and any(not shutil.which(x) for x in ('qsub','singularity')):p.error('Load singularity and run on SGE host')
    prepare(root,dest,not a.prepare_only);print('Output: '+str(dest),flush=True)
    if a.prepare_only:return 0
    base=['qsub','-terse','-V','-cwd','-S','/bin/bash','-j','y','-o',str(dest)]
    response=subprocess.check_output(base+['-N','foodnet_monthly_spatial','-pe','smp','4','-l','h_rt=48:00:00,h_rss=53248M,mem_free=53248M,h_vmem=68G','-t','1-162',str(dest/'run.sh')],universal_newlines=True).strip()
    (dest/'submission.json').write_text(json.dumps(dict(array_response=response),indent=2)+'\n');match=re.match(r'^(\d+)(?:[.\s]|$)',response)
    if not match:raise ValueError('Unexpected submission response; inspect queue before retry')
    collector=subprocess.check_output(base+['-N','foodnet_spatial_collect','-pe','smp','1','-l','h_rt=04:00:00,h_rss=8192M,mem_free=8192M,h_vmem=16G','-hold_jid',match.group(1),str(dest/'collect.sh')],universal_newlines=True).strip()
    (dest/'submission.json').write_text(json.dumps(dict(array_response=response,collector_response=collector),indent=2)+'\n');print('Spatial array: '+response+'; collector: '+collector+'; archive: '+str(dest)+'.tar.gz');return 0
if __name__=='__main__':sys.exit(main())
