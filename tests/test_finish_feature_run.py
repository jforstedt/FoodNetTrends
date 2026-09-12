#!/usr/bin/env python3
"""Verify published-result completion submits only the absent typhoidal group."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

root=Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory() as directory:
    temp=Path(directory);(temp/'scripts').mkdir()
    shutil.copyfile(root/'scripts/finish_feature_run.py',temp/'scripts/finish_feature_run.py')
    spec=importlib.util.spec_from_file_location('finish',str(temp/'scripts/finish_feature_run.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    plan=temp/'output/fixture/validation_plan';plan.mkdir(parents=True)
    results=plan.parent/'spline_results';results.mkdir()
    groups=['STEC~O157','SALMONELLA~ENTERITIDIS','SALMONELLA~TYPHOIDAL']
    params=dict(pathogen_grouping='|'.join(groups),baseline_year=2019,cleanFile='/saved/clean.csv')
    (plan/'params.json').write_text(json.dumps(params))
    (plan/'nextflow.log').write_text('jobId: 123\nWorkflow completed >\n')
    def publish(group):
        prefix=group.replace('~','_');subgroup=group.split('~')[1]
        for suffix in ['_brm.Rds','_IRCatch.csv','_IRSite.csv','_EstIRRCatch_2019_2019.csv','_convergence_diagnostics.csv']:
            (results/(prefix+suffix)).write_text('fixture\n1\n')
        (results/(prefix+'_analysis_settings.csv')).write_text('subgroup,baseline_start,baseline_end\n'+subgroup+',2019,2019\n')
    for group in groups[:-1]:publish(group)
    before={p:p.read_bytes() for p in results.iterdir()}
    def qstat(*args,**kwargs):return subprocess.CompletedProcess(args,0,'job-ID state\n','')
    calls=[]
    def launch(argv,**kwargs):
        calls.append(argv)
        if argv[0]=='nextflow':
            submitted=json.loads(Path(argv[argv.index('-params-file')+1]).read_text())
            assert submitted['pathogen_grouping']=='SALMONELLA~TYPHOIDAL'
            assert submitted['skip_dashboard'] is True and '-resume' not in argv
            publish('SALMONELLA~TYPHOIDAL')
        return 0
    with patch('subprocess.run',qstat),patch('subprocess.call',launch),patch.object(sys,'argv',['finish','fixture']):
        try:module.main()
        except SystemExit as result:assert result.code==0
    assert [c[0] for c in calls]==['nextflow','singularity']
    assert all(p.read_bytes()==value for p,value in before.items())
    calls.clear()
    with patch('subprocess.run',qstat),patch('subprocess.call',launch),patch.object(sys,'argv',['finish','fixture']):
        try:module.main()
        except SystemExit as result:assert result.code==0
    assert [c[0] for c in calls]==['singularity']
    with patch('subprocess.run',lambda *a,**k:subprocess.CompletedProcess(a,0,'123 running\n','')):
        try:module.inspect(temp,'fixture');raise AssertionError('active job accepted')
        except ValueError as error:assert 'still active' in str(error)
    (plan/'nextflow.log').write_text('Running\n')
    try:module.inspect(temp,'fixture');raise AssertionError('active launcher accepted')
    except ValueError as error:assert 'shutdown' in str(error)
print('PASS missing-only submission, preservation of completed files, dashboard-only completion, and active-job/launcher guards.')
