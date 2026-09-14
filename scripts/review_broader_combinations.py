#!/usr/bin/env python3
"""Verify the combined return archive and inventory evidence for scientific review.

Reads archives as data; never executes their scripts or modifies cluster fits.
This is an integrity/identity gate, not model acceptance or a statistical review.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile

PATHOGENS=('CAMPYLOBACTER','CRYPTOSPORIDIUM','CYCLOSPORA','LISTERIA','SALMONELLA','SHIGELLA','STEC','VIBRIO','YERSINIA')
CLASSIFIED=set(PATHOGENS)-{'CRYPTOSPORIDIUM','CYCLOSPORA','LISTERIA'}
LIMIT=1024**3


def decode(raw):
    def pairs(values):
        result={}
        for key,value in values:
            if key in result:raise ValueError('Duplicate JSON key: '+key)
            result[key]=value
        return result
    return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs)


class Archive:
    def __init__(self, source, manifest):
        self.tar=tarfile.open(fileobj=io.BytesIO(source),mode='r:*') if isinstance(source,bytes) else tarfile.open(str(source),'r:*')
        self.files={};total=0
        try:
            for member in self.tar:
                name=member.name;p=PurePosixPath(name)
                if not name or p.is_absolute() or '\\' in name or ':' in name or any(x in ('','..','.') for x in name.split('/')) or not member.isfile() or name in self.files:
                    raise ValueError('Unsafe, nonregular or duplicate member: '+name)
                total+=member.size
                if total>LIMIT:raise ValueError('Archive exceeds 1 GiB uncompressed limit')
                self.files[name]=member
            bound=self.json(manifest)
            if not isinstance(bound,dict) or set(bound)!=set(self.files)-{manifest}:raise ValueError('Incomplete archive manifest')
            for name,digest in bound.items():
                if hashlib.sha256(self.read(name)).hexdigest()!=digest:raise ValueError('Changed archive member: '+name)
        except Exception:
            self.tar.close();raise
    def read(self,name):
        if name not in self.files:raise ValueError('Missing archive member: '+name)
        return self.tar.extractfile(self.files[name]).read()
    def json(self,name):return decode(self.read(name))
    def close(self):self.tar.close()


def identities(branch):
    if branch=='classification':return {p:dict(pathogen=p) for p in CLASSIFIED}
    expected={}
    for p in PATHOGENS:
        for c in ((2011,2013,2014) if p=='CRYPTOSPORIDIUM' else (2011,2013,2016)):
            for model in (('spline',) if branch=='inspection' else ('rw1','ar1','spline')):
                for seasonal in (False,True):
                    for spatial in (('iid',) if branch=='inspection' else ('iid','bym2')):
                        name='{}_{}_{}_{}'.format(p,c,model,'seasonal' if seasonal else 'nonseasonal')+('_bym2' if spatial=='bym2' else '')
                        expected[name]=dict(pathogen=p,cutoff=c,temporal=model,seasonal=seasonal,spatial=spatial)
    return expected


def inspect_branch(branch, report):
    plan,summary=report.json('plan.json'),report.json('summary.json')
    versions={'spatial':'monthly_spatial_factorial_v1','classification':'classification_monthly_preparation_v1','inspection':'monthly_spline_inspection_v1'}
    if plan.get('version')!=versions[branch] or plan.get('verified') is not True:raise ValueError('Unexpected/unverified '+branch+' plan')
    expected=identities(branch);tasks=plan.get('tasks',[])+plan.get('references',[])
    if len(tasks)!=len(expected) or {t['id'] for t in tasks}!=set(expected):raise ValueError('Wrong '+branch+' task matrix')
    for t in tasks:
        fields=('cutoff','seasonal') if branch=='inspection' else (('pathogen','cutoff','seasonal','temporal','spatial') if branch=='spatial' else ())
        for field in fields:
            if t.get(field)!=expected[t['id']][field]:raise ValueError('Changed task identity: '+t['id'])
        if branch=='spatial' and t.get('reused') is not (t['spatial']=='iid'):raise ValueError('Changed reuse identity')
    results=summary.get('tasks',[])
    if len(results)!=len(expected) or {r.get('task') for r in results}!=set(expected):raise ValueError('Wrong summary task identities')
    complete=sum(r.get('status')=='COMPLETE' for r in results)
    if branch!='classification' and summary.get('complete')!=complete:raise ValueError('Inconsistent complete count')
    ready=complete==len(expected) and not summary.get('issues')
    if branch=='classification' and summary.get('execution_complete') is not ready:raise ValueError('Inconsistent classification completion')
    # Recheck frozen portable inputs and task output bindings, not just the final manifest.
    roots=[p.rsplit('/scripts/',1)[0] for p in plan.get('inputs',{}) if p.endswith('/scripts/'+{'spatial':'launch_monthly_spatial_factorial.py','classification':'launch_classification_monthly_preparation.py','inspection':'launch_monthly_spline_inspection.py'}[branch])]
    if len(roots)!=1:raise ValueError('Cannot identify snapshot root')
    root=roots[0]+'/'
    for absolute,digest in plan['inputs'].items():
        if absolute.startswith(root):
            name=absolute[len(root):]
            if hashlib.sha256(report.read(name)).hexdigest()!=digest:raise ValueError('Changed frozen input: '+name)
    plan_digest=hashlib.sha256(report.read('plan.json')).hexdigest()
    for r in results:
        if r.get('status')!='COMPLETE':continue
        t=next(t for t in tasks if t['id']==r['task'])
        if t.get('reused'):continue
        record=report.json(t['id']+'/task_status.json')
        if record.get('task')!=t['id'] or record.get('status')!='COMPLETE' or record.get('exit_status')!=0 or record.get('plan_sha256')!=plan_digest:raise ValueError('Invalid task completion record')
        if not record.get('outputs'):raise ValueError('Missing task output bindings')
        for name,digest in record['outputs'].items():
            local=t['id']+'/'+name
            if '_INTERNAL' in PurePosixPath(name).name:continue
            if PurePosixPath(name).suffix.lower() not in ('.csv','.json','.txt','.log','.py','.r','.sh','.md'):continue
            if hashlib.sha256(report.read(local)).hexdigest()!=digest:raise ValueError('Changed task output: '+local)
    return dict(expected=len(expected),complete=complete,execution_complete=ready,files_verified=len(report.files),issues=summary.get('issues',[]),scientific_acceptance=False)


def review(source,output):
    output=Path(output)
    if output.exists():raise ValueError('Review output already exists')
    outer=Archive(source,'archive_sha256.json');result=dict(branches={},issues=[],scientific_acceptance=False)
    try:
        summary=outer.json('summary.json')
        for branch in ('spatial','classification','inspection'):
            filename=branch+'.tar.gz'
            if filename not in outer.files:
                result['branches'][branch]=dict(execution_complete=False,reason='Missing branch archive')
                result['issues'].append('Missing '+branch+' archive');continue
            inner=Archive(outer.read(filename),'report_sha256.json')
            try:
                if inner.json('summary.json')!=summary.get('branches',{}).get(branch,{}).get('summary'):raise ValueError('Outer/inner summary mismatch: '+branch)
                result['branches'][branch]=inspect_branch(branch,inner)
            finally:inner.close()
        result['issues'].extend(summary.get('issues',[]))
        result['execution_complete']=not result['issues'] and all(r['execution_complete'] for r in result['branches'].values())
        if summary.get('execution_complete') is not result['execution_complete']:raise ValueError('Outer completion claim differs')
        result['archive_sha256']=hashlib.sha256(Path(source).read_bytes()).hexdigest()
    finally:outer.close()
    output.mkdir(parents=True)
    (output/'intake.json').write_text(json.dumps(result,indent=2)+'\n')
    lines=['# Combined experiment intake','', 'Archive integrity and task identity checks completed. Statistical review remains pending.','']
    for name,r in result['branches'].items():lines.append('- {}: {} of {} complete.'.format(name,r.get('complete',0),r.get('expected','unknown')))
    lines+=['','Next review steps:','', '- Spatial: independently recompute paired contrasts; inspect bias, interval coverage, widths, tails and Monte Carlo stability alongside score differences.', '- Classification: reconcile monthly and annual counts, missing dates and zero denominators before fitting conditional-binomial combinations.', '- Saved splines: examine linear/nonlinear temporal extrapolation across all pathogens; component means do not provide joint uncertainty.', '', 'No model is accepted and no fit is changed by this intake.']
    (output/'review_queue.md').write_text('\n'.join(lines)+'\n')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive');p.add_argument('--output',required=True);a=p.parse_args()
    try:result=review(a.archive,a.output)
    except (OSError,ValueError,KeyError,TypeError,tarfile.TarError) as e:p.error(str(e))
    print(json.dumps(result,indent=2));return 0 if result['execution_complete'] else 1
if __name__=='__main__':raise SystemExit(main())
