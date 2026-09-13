#!/usr/bin/env python3
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from county_forecast_protocol import validate_source


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()


def rows(path):
    with Path(path).open(newline='') as f:return list(csv.DictReader(f))


def validate(dest,task):
    out=Path(dest)/task['id']/'result';kind=task['kind']
    marker={'basis':'SPLINE_BATCH_BASIS_COMPLETE','gate':'SPLINE_NUMERICAL_GATE_PASS','sampling':'SAVED_FORECAST_SAMPLING_COMPLETE',
            'definitions':'EXTENSION_DEFINITIONS_COMPLETE','cyclospora':'CYCLOSPORA_DIAGNOSTIC_COMPLETE','spline':'COUNTY_SPLINE_PILOT_COMPLETE'}[kind]
    if (out/'status.txt').read_text().splitlines()[0]!=marker:raise ValueError('Missing completion marker')
    required={'basis':['basis_2011.rds','basis_2013.rds','basis_2016.rds','synthetic/basis1.rds','synthetic/basis3.rds'],
      'gate':['spline_gate_checks.csv','spline_gaussian_reference.csv'],'sampling':['seed_state_year_scores.csv','seed_cells_INTERNAL.csv','cell_stability_INTERNAL.csv','settings.csv','inputs.csv'],
      'definitions':['date_checks.csv','date_intervals.csv','test_codes.csv','category_test_crosswalk.csv','laboratory_consistency.csv','identifier_support.csv'],
      'cyclospora':['diagnostic_specification.txt','state_year_counts_INTERNAL.csv','diagnostic_fit_INTERNAL.rds'],
      'spline':['heldout_cells_INTERNAL.csv','heldout_scores_INTERNAL.csv','heldout_aggregate_checks_INTERNAL.csv','spline_specification.csv','split.csv','input_checksums.csv','fit_INTERNAL.rds']}[kind]
    if any(not(out/n).is_file() or not(out/n).stat().st_size for n in required):raise ValueError('Missing required output')
    def finite(value):
        x=float(value)
        if not math.isfinite(x):raise ValueError('Nonfinite numerical artifact')
        return x
    if kind=='gate':
        checks=rows(out/'spline_gate_checks.csv')
        if len(checks)!=2 or {r['model'] for r in checks}!={'iid','spatial'} or any(r['status']!='PASS' for r in checks):raise ValueError('Numerical gate did not pass')
        for r in checks:
            if any(not 0<=finite(r[k])<.02 for k in ('standardized_mean_change','relative_sd_change','heldout_mask_change')):raise ValueError('Spline gate tolerance exceeded')
        reference=rows(out/'spline_gaussian_reference.csv')
        if len(reference)!=1 or reference[0]['status']!='PASS' or any(not 0<=finite(reference[0][k])<1e-4 for k in ('mean_error','sd_error')):raise ValueError('Gaussian reference failed')
    if kind in ('sampling','spline'):
        audit=Path(task['source']['audit']);nodes=rows(audit/'reports/graph_nodes.csv')
        mapping={r['fips']:r['state'] for r in nodes};years={str(task['origin']+i) for i in (1,2,3)}
        expected={(f,state,y) for f,state in mapping.items() for y in years}
        if len(nodes)!=486 or len(mapping)!=486:raise ValueError('County footprint mismatch')
    if kind=='sampling':
        settings=rows(out/'settings.csv')
        if len(settings)!=1 or int(settings[0]['origin'])!=task['origin'] or int(settings[0]['horizon'])!=3 or int(settings[0]['draws_per_seed'])<4000 or settings[0]['refitted']!='FALSE' or settings[0].get('model')!=task['model']:raise ValueError('Sampling specification mismatch')
        seeds=set(settings[0]['seeds'].split(';'))
        if len(seeds)!=4:raise ValueError('Missing independent streams')
        data=rows(out/'seed_cells_INTERNAL.csv');expected_cells={(f,st,y,seed) for f,st,y in expected for seed in seeds}
        keys={(r['fips'],r['state'],r['year'],r['seed']) for r in data}
        if len(data)!=len(expected_cells) or keys!=expected_cells:raise ValueError('Incomplete sampling cell grid')
        sums={};counts={}
        for r in data:
            score=finite(r['log_predictive_density']);err=finite(r['density_relative_mcse'])
            if err<0:raise ValueError('Negative MCSE')
            key=(r['seed'],r['state'],r['year']);sums[key]=sums.get(key,0)+score;counts[key]=counts.get(key,0)+1
        scores=rows(out/'seed_state_year_scores.csv');keys={(r['seed'],r['state'],r['year']) for r in scores}
        if len(scores)!=len(sums) or keys!=set(sums):raise ValueError('Incomplete state/year/seed scores')
        for r in scores:
            key=(r['seed'],r['state'],r['year'])
            if int(r['cells'])!=counts[key] or not math.isclose(finite(r['sum_log_predictive_density']),sums[key],rel_tol=1e-9,abs_tol=1e-7):raise ValueError('State/year scores differ from cell scores')
    if kind=='spline':
        data=rows(out/'heldout_cells_INTERNAL.csv');keys={(r['fips'],r['state'],r['year']) for r in data}
        if len(data)!=len(expected) or keys!=expected:raise ValueError('Incomplete heldout county cells')
        for r in data:
            vals=[finite(r[k]) for k in ('lower95','lower50','median','upper50','upper95')]
            if vals!=sorted(vals) or vals[0]<0 or finite(r['population'])<=0 or finite(r['observed'])<0:raise ValueError('Invalid forecast interval/population/count')
            if finite(r['observed'])!=int(finite(r['observed'])) or finite(r['mean_expected'])<0 or finite(r['density_relative_mcse'])<0:raise ValueError('Invalid count/expectation/MCSE')
            finite(r['log_predictive_density'])
        split=rows(out/'split.csv')
        if len(split)!=1 or int(split[0]['train_end'])!=task['origin'] or split[0]['variant']!=task['variant'] or split[0]['heldout_counts_masked']!='TRUE':raise ValueError('Spline split mismatch')
    return True


def prerequisite(dest,plan,name):
    task=next(t for t in plan['tasks'] if t['id']==name);work=dest/name
    record=json.loads((work/'task_status.json').read_text())
    if record.get('status')!='COMPLETE' or record.get('exit_status')!=0:raise ValueError('Prerequisite did not complete: '+name)
    if not record.get('outputs') or any(sha(work/p)!=h for p,h in record['outputs'].items()):raise ValueError('Prerequisite output changed: '+name)
    validate(dest,task)


def run(dest,name):
    dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());task=next(t for t in plan['tasks'] if t['id']==name)
    work=dest/name;work.mkdir(exist_ok=False);r=dict(task=name,kind=task['kind'],status='FAILED',exit_status=1)
    inputs=dict(plan['fingerprints']);inputs.update(task.get('inputs',{}))
    try:
        if not plan['verified']:raise ValueError('Unverified plan cannot execute')
        for p,h in inputs.items():
            if sha(p)!=h:raise ValueError('Changed source/input: '+p)
        if task.get('source'):validate_source(task['pathogen'],task['source'])
        for dep in task.get('requires',[]):prerequisite(dest,plan,dep)
        with (work/'task.log').open('w') as log:
            for cmd in task['commands']:
                code=subprocess.run(cmd,cwd=str(dest),stdout=log,stderr=subprocess.STDOUT).returncode
                if code:raise ValueError('Command exit status '+str(code))
        validate(dest,task)
        for p,h in inputs.items():
            if sha(p)!=h:raise ValueError('Input changed during work: '+p)
        for dep in task.get('requires',[]):prerequisite(dest,plan,dep)
        if task.get('source'):validate_source(task['pathogen'],task['source'])
        r.update(status='COMPLETE',exit_status=0,outputs={str(p.relative_to(work)):sha(p) for p in (work/'result').rglob('*') if p.is_file() and (p.suffix.lower() in ('.csv','.txt','.json') or task['kind']=='basis')})
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as e:r['reason']=str(e)
    (work/'task_status.json').write_text(json.dumps(r,indent=2)+'\n');return r['exit_status']


if __name__=='__main__':sys.exit(run(sys.argv[1],sys.argv[2]))
