#!/usr/bin/env python3
"""End-to-end feature contracts using synthetic cases and deterministic model draws."""
import csv
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent

def run(argv):
    if argv[0] == "Rscript":
        argv = shlex.split(os.environ.get("FOODNET_RSCRIPT", "Rscript")) + argv[1:]
    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout

def main():
    with tempfile.TemporaryDirectory(prefix='foodnet-feature-matrix-') as directory:
        temp = Path(directory)
        fields = ['pathogen','year','state','county','siteid','cxcidt','travelint','serotypesummary2','stec_class','dxo157','pathogentype']
        # Expected membership is specified independently of the classification code.
        examples = [
            ('SALMONELLA','ENTERITIDIS','','', 'ENTERITIDIS'),
            ('SALMONELLA','NEWPORT','','', 'OTHER SEROTYPES'),
            ('SALMONELLA','I 4,[5],12:i:-','','', 'I 4,[5],12:i:-'),
            ('SALMONELLA','','','', 'NOT SEROTYPED'),
            ('SALMONELLA','TYPHI','','', 'TYPHOIDAL'),
            ('SALMONELLA','PARATYPHI A','','', 'TYPHOIDAL'),
            ('SALMONELLA','PARATYPHI C','','', 'TYPHOIDAL'),
            ('SALMONELLA','PARATYPHI B TARTRATE-NEGATIVE','','', 'TYPHOIDAL'),
            ('SALMONELLA','PARATYPHI B','','', 'UNCLASSIFIED'),
            ('STEC','','STEC NONO157','POSITIVE', 'O157'),
            ('STEC','','STEC O157','NEGATIVE', 'nonO157'),
            ('STEC','','STEC O157','UNKNOWN', 'O157'),
            ('STEC','','STEC O AG UNDET','UNKNOWN', 'NOT SEROGROUPED'),
            ('CAMPYLOBACTER','JEJUNI','','', 'JEJUNI'),
            ('CAMPYLOBACTER','COLI','','', 'COLI'),
            ('CAMPYLOBACTER','','','', 'unselected'),
        ]
        cases = temp/'clean.csv'
        with cases.open('w') as handle:
            writer = csv.writer(handle); writer.writerow(fields)
            for year in range(2010,2020):
                for pathogen, serotype, stec, dx, _ in examples:
                    writer.writerow([pathogen,year,'CA','ALAMEDA','CA','CX+','NO',serotype,stec,dx,'Bacterial'])
        pop = temp/'population.csv'
        with pop.open('w') as handle:
            writer=csv.writer(handle); writer.writerow(['year','state','population'])
            for year in range(2010,2020):
                for state in ['CA','OR']: writer.writerow([year,state,100000])
        expected = [('SALMONELLA','ENTERITIDIS',1),('SALMONELLA','I 4,[5],12:i:-',1),
                    ('SALMONELLA','OTHER SEROTYPES',6),('SALMONELLA','NOT SEROTYPED',1),
                    ('SALMONELLA','TYPHOIDAL',4),('SALMONELLA','NONTYPHOIDAL',3),
                    ('SALMONELLA','UNCLASSIFIED',2),('STEC','O157',2),('STEC','nonO157',1),
                    ('STEC','NOT SEROGROUPED',1),('CAMPYLOBACTER','JEJUNI',1),('CAMPYLOBACTER','COLI',1)]
        output=temp/'results'/'spline_results'
        for index,(pathogen,group,n) in enumerate(expected):
            start,end=(2019,2019) if index%2 else (2016,2018)
            run(['Rscript',str(ROOT/'tests/mock_model.R'),'--mmwrFile',str(cases),
                 '--cleanFile',str(cases),'--preprocessed','TRUE','--censusFileB',str(pop),
                 '--censusFileP',str(pop),'--pathogen',pathogen,'--subgroup',group,
                 '--selected_serotypes','ENTERITIDIS|I 4,[5],12:i:-','--baseline_start',str(start),
                 '--baseline_end',str(end),'--outDir',str(output),'--projID','acceptance',
                 '--classification_rules',str(ROOT/'analysis_configs/classification_rules.csv')])
            prefix=re.sub('_+','_',re.sub('[^a-zA-Z0-9_-]','_',pathogen+'_'+group)).rstrip('_')
            assert not (output/(prefix+'_error.txt')).exists(), prefix
            with (output/(prefix+'_EstIRRCatch_{}_{}.csv'.format(start,end))).open() as handle:
                rows=list(csv.DictReader(handle))
            assert len(rows)==10,prefix
            for row in rows:
                assert int(row['baseline_start'])==start and int(row['baseline_end'])==end
                assert abs(float(row['raw_count'])-n)<1e-8,(prefix,row)
                # OR has no cases but contributes its surveyed population.
                assert float(row['population'])==200000,(prefix,row)
                assert abs(float(row['baseline_raw_ir'])-n/2)<1e-8,(prefix,row)
                assert float(row['baseline_median_ir'])>0
            print('PASS {} / {} / baseline {}-{}'.format(pathogen,group,start,end),flush=True)
        # A nominally converged fit with warnings must not get a clean badge.
        warning_file=output/'SALMONELLA_ENTERITIDIS_convergence_diagnostics.csv'
        warning_file.write_text('converged,warnings,max_rhat,min_ess\nTRUE,DIVERGENCE WARNING: 12 divergent transitions,1.001,4000\n')
        html=temp/'dashboard.html' 
        run(['Rscript',str(ROOT/'dashboard/generate_dashboard.R'),'--output_dir',str(output.parent),
             '--projID','acceptance','--output',str(html)])
        payload=json.loads(re.search(r'window.DASHBOARD_DATA = (.*?);\n',html.read_text()).group(1))
        analyses=payload['analyses']
        assert len(analyses)==len(expected),(len(analyses),len(expected))
        assert all(a['status']=='success' and a['convergence_status']==('Review diagnostics' if a['subgroup']=='ENTERITIDIS' else 'Not converged') for a in analyses.values())
        assert {a['subgroup'] for a in analyses.values()}=={g for _,g,_ in expected}
        assert all(a['irr'] and a['settings'] for a in analyses.values())
        print('PASS dashboard includes all 12 groups, baselines, and diagnostic status')

if __name__=='__main__': main()
