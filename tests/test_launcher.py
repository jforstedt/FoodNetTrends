#!/usr/bin/env python3
"""Exercise menu choices without loading cluster modules or launching jobs."""
import subprocess
from pathlib import Path

script = Path('run_workflow.sh').read_text()
function = script[script.index('handle_pathogen_grouping() {'):script.index('\nextract_states_from_data()')]
code = 'classification_rules=analysis_configs/classification_rules.csv\nserotype_source=auto\n' + function
code += '\nhandle_pathogen_grouping "$1" "$2"\n'

def menu(pathogen, answers, data=''):
    p = subprocess.run(['bash','-c',code,'menu-test',pathogen,data],
                       input=answers,text=True,capture_output=True,check=True)
    return p.stdout.strip()

preset=menu('SALMONELLA','4\n').split('|')
assert len(preset)==7
assert 'SALMONELLA~I 4,[5],12:i:-' in preset
assert preset[-2:]==['SALMONELLA~OTHER SEROTYPES','SALMONELLA~NOT SEROTYPED']
assert menu('STEC','6\n')=='STEC~NOT SEROGROUPED'
assert len(menu('STEC','7\n').split('|'))==4
assert menu('SALMONELLA','2\nENTERITIDIS|I 4,[5],12:i:-\ny\ny\n')==(
    'SALMONELLA~ENTERITIDIS|SALMONELLA~I 4,[5],12:i:-|SALMONELLA~OTHER SEROTYPES|SALMONELLA~NOT SEROTYPED')
assert menu('CAMPYLOBACTER','y\nJEJUNI|COLI\n')=='CAMPYLOBACTER~JEJUNI|CAMPYLOBACTER~COLI'
assert menu('SALMONELLA','2\n999\n1\nn\nn\n','test_data/test_mmwr.csv')=='SALMONELLA~Typhimurium'
assert menu('SALMONELLA','6\n')=='SALMONELLA~TYPHOIDAL|SALMONELLA~NONTYPHOIDAL|SALMONELLA~UNCLASSIFIED'
print('Launcher preset, custom, species, STEC and invalid-selection tests passed.')

# Missing HPC paths must be corrected or cancelled before setup proceeds.
helpers=script[script.index('resolve_input_file() {'):script.index('handle_pathogen_grouping() {')]
import tempfile
with tempfile.TemporaryDirectory() as temp:
    actual=Path(temp)/'current data.sas7bdat'
    actual.touch()
    p=subprocess.run(['bash','-c',helpers+'\nresolve_input_file MMWR "$1"','path-test','/missing/old.sas7bdat'],
                     input=str(actual)+'\n',text=True,capture_output=True)
    assert p.returncode==0 and p.stdout.strip()==str(actual)
    p=subprocess.run(['bash','-c',helpers+'\nresolve_input_file MMWR "$1"','path-test','/missing/old.sas7bdat'],
                     input='\n',text=True,capture_output=True)
    assert p.returncode!=0
    p=subprocess.run(['bash','-c',helpers+'\nresolve_input_file MMWR "$1"','path-test',str(actual)],
                     input='',text=True,capture_output=True)
    assert p.returncode==0 and not p.stderr
for mode,label in [('test','Test'),('publication','Publication'),('max','Max'),('custom','Custom'),
                   ('resume','Resume previous run'),('preprocess','Preprocessing only')]:
    p=subprocess.run(['bash','-c',helpers+'\nrun_mode_label "$1"','mode-test',mode],
                     text=True,capture_output=True,check=True)
    assert p.stdout.strip()==label
print('Input-path correction/cancellation and all six mode labels passed.')
