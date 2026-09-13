#!/usr/bin/env python3
"""Launch parallel numerical screens followed by gated exploratory county hindcasts."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
from county_forecast_protocol import build_protocol
from run_county_forecast_validation import sha

SCRIPTS=('county_forecast_protocol.py','fit_county_pilot.R','diagnose_saved_county_pilot.R','county_sensitivity.R','county_forecast_model.R',
 'county_forecast_check.R','county_forecast_reference.R','county_forecast_artifacts.py','county_forecast_calibration.R','county_forecast_historical_reference.R',
 'run_county_forecast_comparison.R','collect_county_forecast_calibration.py','run_county_forecast_validation.py','collect_county_forecast_validation.py')

def prepare(root,dest,container,verify=True,replicates=20):
    if replicates<20:raise ValueError('At least 20 independent replicates per scenario are required')
    protocol=build_protocol(root,verify_inputs=verify)
    dest.mkdir(parents=True,exist_ok=False);scripts=dest/'scripts';scripts.mkdir();(dest/'tests').mkdir()
    for name in SCRIPTS:shutil.copyfile(str(root/'scripts'/name),str(scripts/name))
    shutil.copyfile(str(root/'tests/test_county_forecast_invariance.R'),str(dest/'tests/test_county_forecast_invariance.R'))
    q=shlex.quote
    common=['singularity','exec','--cleanenv','--env','OPENBLAS_NUM_THREADS=1,OMP_NUM_THREADS=2,MKL_NUM_THREADS=1','--bind','/scicomp',str(container),'Rscript','--vanilla']
    horizon=dest/'horizon';horizon.mkdir()
    tasks=[dict(id='horizon',kind='horizon',command=common+[str(dest/'tests/test_county_forecast_invariance.R'),str(horizon/'result')])]
    tasks.append(dict(id='reference',kind='reference',command=common+[str(scripts/'county_forecast_reference.R'),str(dest/'reference/result')]))
    for density in ('sparse','dense'):
        for variant in ('spatial','iid'):
            for replicate in range(1,replicates+1):
                name='calibration_%s_%s_%03d'%(density,variant,replicate)
                tasks.append(dict(id=name,kind='calibration',density=density,variant=variant,replicate=replicate,
                  command=common+[str(scripts/'county_forecast_calibration.R'),'task',str(dest/name/'result'),density,variant,str(replicate),'2000','2']))
    for task in protocol['tasks']:
        work=dest/task['id'];source=protocol['sources'][task['pathogen']]
        task['input_fingerprints']=dict(source.get('evidence_sha256',{}))
        if verify:task['input_fingerprints'][str(Path(task['audit'])/'county_panel_INTERNAL.rds')]=source['panel_sha256']
        task['command']=common+[str(scripts/'run_county_forecast_comparison.R'),task['audit'],task['reconciliation'],str(work/'result'),task['model'],'8',str(task['origin']),str(task['horizon'])]
        tasks.append(task)
    (dest/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    # Gate only permits exploratory comparisons. It does not certify predictive coverage.
    gate='''import json, pathlib, subprocess, sys
from run_county_forecast_validation import sha
from county_forecast_artifacts import validate_task_outputs
p=pathlib.Path(sys.argv[1]);m=json.loads((p/'manifest.json').read_text())
issues=[]
if not m.get('inputs_verified'):issues.append('Real inputs were not verified during preparation')
for t in m['tasks']:
 if t['kind']=='forecast':continue
 f=p/t['id']/'task_status.json'
 if not f.exists():issues.append('Incomplete prerequisite '+t['id']);continue
 record=json.loads(f.read_text())
 if record.get('status')!='COMPLETE' or record.get('exit_status')!=0:issues.append('Failed prerequisite '+t['id']);continue
 try:
  validate_task_outputs(p/t['id'],t)
  if not record.get('outputs') or any(sha(p/t['id']/name)!=h for name,h in record['outputs'].items()):issues.append('Changed prerequisite output '+t['id'])
 except (OSError,ValueError,KeyError) as e:issues.append(str(e))
for f,h in m['fingerprints'].items():
 if sha(f)!=h:issues.append('Changed source/container '+f)
status='REVIEW_REQUIRED'
if not issues:
 code=subprocess.run(m['calibration_collect_command'],cwd=str(p)).returncode
 f=p/'calibration_summary.json'
 if code==0 and f.exists() and json.loads(f.read_text()).get('status')=='NUMERICAL_SCREEN_PASS':status='PASS'
 else:issues.append('Calibration numerical screen did not pass')
result=dict(status=status,issues=issues,manifest_sha256=sha(p/'manifest.json'),scope='Allows exploratory hindcasts only; no scientific adoption')
tmp=p/'gate.json.tmp';tmp.write_text(json.dumps(result,indent=2)+'\\n');tmp.replace(p/'gate.json')
print(json.dumps(result,indent=2));sys.exit(0 if status=='PASS' else 1)
'''
    (scripts/'gate.py').write_text(gate)
    fingerprints={str(p):sha(p) for p in list(scripts.iterdir())+list((dest/'tests').iterdir())}
    if container.exists():fingerprints[str(container)]=sha(container)
    plan=dict(tasks=tasks,protocol_version=protocol['protocol_version'],fingerprints=fingerprints,
      inputs_verified=verify,replicates_per_scenario=replicates,calibration_draws=2000,
      calibration_collect_command=['python3',str(scripts/'collect_county_forecast_calibration.py'),str(dest),'--replicates',str(replicates)],
      scientific_status='EXPLORATORY; simulation screen and reused historical data do not certify forecast accuracy',
      no_state_model_reruns=True,no_dashboard_promotion=True)
    (dest/'manifest.json').write_text(json.dumps(plan,indent=2)+'\n')
    for kind in ('horizon','reference','calibration','forecast'):
        items=[t['id'] for t in tasks if t['kind']==kind]
        text='#!/bin/bash\nset -euo pipefail\ncase "${SGE_TASK_ID:-1}" in\n'
        for i,name in enumerate(items,1):text+=str(i)+') task='+q(name)+';;\n'
        text+='*) exit 2;;\nesac\nexec python3 '+q(str(scripts/'run_county_forecast_validation.py'))+' '+q(str(dest))+' "$task"\n'
        (dest/(kind+'.sh')).write_text(text)
    (dest/'gate.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec python3 '+q(str(scripts/'gate.py'))+' '+q(str(dest))+'\n')
    (dest/'collect.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec python3 '+q(str(scripts/'collect_county_forecast_validation.py'))+' '+q(str(dest))+'\n')
    return plan

def main():
    root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepare-only',action='store_true');p.add_argument('--replicates',type=int,default=20);a=p.parse_args()
    container=root/'foodnet-inla-fixed.sif'
    if not a.prepare_only:
        for tool in ('qsub','singularity'):
            if not shutil.which(tool):p.error('Load module for '+tool)
        if not container.is_file():p.error('Missing existing foodnet-inla-fixed.sif')
    dest=root/'output'/('county_forecast_validation_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    print('Checking audit lineage and creating the fixed task matrix...',flush=True)
    try:plan=prepare(root,dest,container,verify=not a.prepare_only,replicates=a.replicates)
    except (ValueError,KeyError,OSError) as e:p.error(str(e))
    print('Output: '+str(dest)+'\nCalibration fits: '+str(4*a.replicates)+'\nGated county fits: 54',flush=True)
    if a.prepare_only:print('UNVERIFIED preparation only; no submission.');return
    submitted={}
    def submit(kind,cpus,count=None,hold=None):
        resources='h_rt=24:00:00,h_rss=32768M,mem_free=32768M,h_vmem=64G' if kind=='forecast' else 'h_rt=04:00:00,h_rss=4096M,mem_free=4096M,h_vmem=8G'
        cmd=['qsub','-terse','-V','-cwd','-S','/bin/bash','-N','foodnet_validation_'+kind,'-pe','smp',str(cpus),
          '-l',resources,'-j','y','-o',str(dest/(kind+'.log'))]
        if count:cmd+=['-t','1-'+str(count)]
        if hold:cmd+=['-hold_jid',','.join(hold)]
        value=subprocess.check_output(cmd+[str(dest/(kind+'.sh'))],universal_newlines=True).strip()
        match=re.match(r'^(\d+)(?:[.\s]|$)',value)
        if not match:raise RuntimeError('Unexpected scheduler response: '+value)
        submitted[kind]=match.group(1);(dest/'submission.json').write_text(json.dumps(submitted,indent=2)+'\n')
        print(kind+' job: '+value,flush=True);return match.group(1)
    h=submit('horizon',2);r=submit('reference',2);c=submit('calibration',2,4*a.replicates)
    g=submit('gate',2,hold=[h,r,c]);f=submit('forecast',8,54,hold=[g]);submit('collect',1,hold=[f])
    print('Final log: '+str(dest/'collect.log')+'\nArchive: '+str(dest)+'.tar.gz\nJobs continue independently of the terminal after all six job IDs appear.')
if __name__=='__main__':main()
