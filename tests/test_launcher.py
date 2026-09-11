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
