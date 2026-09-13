#!/usr/bin/env python3
"""Assemble seven accepted state corrections without fitting or replacing old dashboards."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import shlex
import shutil
import subprocess
from collect_surveillance_refits import validate_proof,validate_outputs,sha256

AUDIT='surveillance_postrun_audit_20260913_034836_194880'
REFITS='surveillance_sampler_refits_20260913_124503_193931'
EXPECTED={'CAMPYLOBACTER_combined','LISTERIA_combined','SHIGELLA_combined','VIBRIO_combined','YERSINIA_combined','STEC_nonO157','YERSINIA_ENTEROCOLITICA'}

def selection(audit,refits):
    audit=Path(audit);refits=Path(refits)
    oldreview=json.loads((audit/'review_summary.json').read_text());source=Path(oldreview['source_run'])
    old=json.loads((source/'manifest.json').read_text());new=json.loads((refits/'manifest.json').read_text())
    report=json.loads((refits/'review_summary.json').read_text())
    if json.loads((audit/'listeria_input_audit.json').read_text())['status']!='PASS':raise ValueError('Listeria audit did not pass')
    passed={r['analysis'] for r in oldreview['results'] if r['status']=='CHECKS_PASS'}
    replacements={r['analysis'] for r in report['results'] if r['status']=='CHECKS_PASS'}
    if len(report['results'])!=len(new['jobs']) or replacements!={j['prefix'] for j in new['jobs']}:raise ValueError('Replacement fits did not all pass')
    selected={}
    for j in old['jobs']:
        if j['prefix'] in passed:selected[j['prefix']]=(source/j['task'],audit/j['task']/'saved_fit_validation.json',j)
    for j in new['jobs']:
        if j['prefix'] in selected:raise ValueError('Unexpected replacement of a passing fit')
        work=refits/j['task'];identity=json.loads((work/(j['prefix']+'_identity_check.json')).read_text())
        if not identity['checks'] or not all(v is True for v in identity['checks'].values()):raise ValueError('Model identity check failed')
        selected[j['prefix']]=(work,work/'saved_fit_validation.json',j)
    if set(selected)!=EXPECTED:raise ValueError('Expected exactly the seven accepted corrections')
    return selected

def prepare(root,audit,refits,dest):
    selected=selection(audit,refits);records={}
    # Recheck checkpoints and tables before copying any results.
    for key,(work,proof,j) in selected.items():
        out=work/'spline_results';s=j['settings'];first=j['first_year'];last=j['last_year']
        model=validate_proof(proof,out/(key+'_brm.Rds'),first,last)
        validate_outputs(out,key,model,first,last,int(s['baseline_start']),int(s['baseline_end']))
        records[key]=dict(source=str(work),fit_sha256=sha256(out/(key+'_brm.Rds')),
                          years=[first,last],baseline=[int(s['baseline_start']),int(s['baseline_end'])])
    dest.mkdir(parents=True,exist_ok=False);results=dest/'spline_results';results.mkdir();proofs=dest/'validation';proofs.mkdir()
    for key,(work,proof,j) in selected.items():
        copied={}
        for f in (work/'spline_results').glob(key+'_*'):
            if f.is_file() and f.suffix.lower()=='.csv':
                target=results/f.name;shutil.copyfile(str(f),str(target));copied[f.name]=sha256(target)
        records[key]['table_sha256']=copied
        shutil.copyfile(str(proof),str(proofs/(key+'.json')))
    manifest=dict(analysis_sources=records,scope='Seven accepted surveillance corrections; not the complete original pathogen/feature inventory.',
                  model_refitted=False,baseline_note='Per-analysis baselines retained: combined analyses 2016–2018; feature subgroups 2019.',source_audit=str(audit),source_refits=str(refits))
    (dest/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    for name in ('bin/functions.R','scripts/finalize_accepted_state_dashboard.R'):
        shutil.copyfile(str(root/name),str(dest/Path(name).name))
    shutil.copytree(str(root/'dashboard'),str(dest/'dashboard_code'))
    # Snapshot generator and template together. Generator resolves template beside itself.
    clean=root/'output/20260911_140750/preprocessed/clean_mmwr.csv'
    q=shlex.quote;common=['singularity','exec','--cleanenv','--env','OPENBLAS_NUM_THREADS=2,OMP_NUM_THREADS=2,MKL_NUM_THREADS=2','--bind','/scicomp',str(root/'foodnet.sif'),'Rscript','--vanilla']
    cmds=[common+[str(dest/'finalize_accepted_state_dashboard.R'),str(dest)],common+[str(dest/'dashboard_code/generate_dashboard.R'),'--output_dir',str(dest),'--projID',dest.name,'--output',str(dest/'dashboard.html'),'--cleanFile',str(clean)]]
    finish='''import json, pathlib, tarfile, hashlib, csv
p=pathlib.Path(__file__).resolve().parent
m=json.loads((p/'manifest.json').read_text())
for key,record in m['analysis_sources'].items():
 for name,h in record['table_sha256'].items():
  if hashlib.sha256((p/'spline_results'/name).read_bytes()).hexdigest()!=h:raise SystemExit('Validated table changed: '+name)
f=p/'dashboard.html';s=f.read_text()
if '<body>' not in s:raise SystemExit('Dashboard body missing')
marker='window.DASHBOARD_DATA = '
if marker not in s:raise SystemExit('Dashboard data missing')
data=json.JSONDecoder().raw_decode(s.split(marker,1)[1].lstrip())[0]
if set(data['analyses'])!=set(m['analysis_sources']):raise SystemExit('Dashboard analysis inventory differs')
for key,entry in data['analyses'].items():
 if entry['status']!='success':raise SystemExit('Dashboard analysis failed: '+key)
 for field,suffix in [('ircatch','_IRCatch.csv'),('irsite','_IRSite.csv')]:
  with (p/'spline_results'/(key+suffix)).open() as handle: rows=list(csv.DictReader(handle))
  displayed=entry[field]
  if len(rows)!=len(displayed):raise SystemExit('Dashboard row count differs: '+key)
  for row,value in zip(rows,displayed):
   for name in ['year','state','population','raw_count','median_ir','mean_ir']:
    if name not in row:continue
    if name=='state':same=row[name]==value.get(name)
    else:same=abs(float(row[name])-float(value[name]))<=1e-6*max(1,abs(float(row[name])))
    if not same:raise SystemExit('Displayed value differs: '+key+' '+name)
note='<div style="padding:12px;background:#eef4fa">Seven accepted state corrections. Combined analyses: baseline 2016–2018; feature subgroups: baseline 2019. Per-analysis year ranges apply. This is a corrections dashboard, not the full original inventory or county INLA validation.</div>'
f.write_text(s.replace('<body>','<body>'+note,1))
(p/'completion.json').write_text(json.dumps(dict(status='DASHBOARD_COMPLETE',analyses=len(m['analysis_sources']),validated_tables_unchanged=True,no_sampling=True)))
with tarfile.open(str(p)+'.tar.gz','w:gz') as t:
 for name in ['dashboard.html','manifest.json','completion.json','finalize.log','spline_results','validation']:
  if (p/name).exists():t.add(str(p/name),arcname=name)
print('DASHBOARD COMPLETE: '+str(f));print('Archive: '+str(p)+'.tar.gz')
'''
    (dest/'finish.py').write_text(finish)
    script='#!/bin/bash\nset -euo pipefail\ncd '+q(str(root))+'\n'
    script+='\n'.join(' '.join(map(q,c)) for c in cmds)+'\npython3 '+q(str(dest/'finish.py'))+'\n'
    (dest/'run.sh').write_text(script)
    return dest

def main():
    root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audit',type=Path,default=root/'output'/AUDIT);p.add_argument('--refits',type=Path,default=root/'output'/REFITS);a=p.parse_args()
    for tool in ('qsub','singularity'):
        if not shutil.which(tool):p.error('Load module for '+tool)
    if not (root/'foodnet.sif').is_file():p.error('Missing foodnet.sif')
    dest=root/'output'/('accepted_state_dashboard_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    print('Verifying accepted fits and tables...',flush=True)
    try:prepare(root,a.audit,a.refits,dest)
    except (ValueError,KeyError,OSError) as e:p.error(str(e))
    job=subprocess.check_output(['qsub','-terse','-V','-cwd','-S','/bin/bash','-N','foodnet_accepted_dashboard','-pe','smp','2','-l','h_rt=04:00:00,h_rss=16384M,mem_free=16384M,h_vmem=32G','-j','y','-o',str(dest/'finalize.log'),str(dest/'run.sh')],universal_newlines=True).strip()
    print('Dashboard job: '+job+'\nLog: '+str(dest/'finalize.log')+'\nHTML: '+str(dest/'dashboard.html')+'\nArchive: '+str(dest)+'.tar.gz')
if __name__=='__main__':main()
