#!/usr/bin/env python3
"""Exercise actual model-script control flow with the deterministic Stan substitute."""
import csv
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory(prefix='foodnet-model-flow-') as temp:
    temp = Path(temp)
    with (root/'test_data/test_mmwr.csv').open() as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        rows = list(reader)
    for i, row in enumerate(rows):
        row['travelint'] = 'YES' if i % 2 else 'NO'
    cases = temp/'cases.csv'
    with cases.open('w') as handle:
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        writer.writerows(rows)
    base = ['Rscript','--vanilla',str(root/'tests/mock_model.R'),
            '--mmwrFile',str(cases),'--cleanFile',str(cases),'--preprocessed','TRUE',
            '--censusFileB',str(root/'test_data/test_census_bacterial.csv'),
            '--censusFileP',str(root/'test_data/test_census_parasitic.csv'),
            '--pathogen','SALMONELLA','--classification_rules',str(root/'analysis_configs/classification_rules.csv'),
            '--projID','fixture']
    output=temp/'success'
    p=subprocess.run(base+['--subgroup','Enteritidis','--baseline_start','2019','--baseline_end','2019',
                          '--travel_stratify','true','--outDir',str(output)],capture_output=True,text=True)
    assert p.returncode == 0, p.stdout+p.stderr
    assert not list(output.glob('*_error.txt')),p.stdout+p.stderr
    def read(name):
        with (output/('SALMONELLA_Enteritidis'+name)).open() as handle:
            return list(csv.DictReader(handle))
    combined=read('_IRCatch.csv')
    domestic=read('_domestic_IRCatch.csv')
    travel=read('_travel_IRCatch.csv')
    assert len(combined)==len(domestic)==len(travel)==10
    for all_row, dom_row, trv_row in zip(combined,domestic,travel):
        assert all_row['population']==dom_row['population']==trv_row['population']
        assert float(all_row['raw_count'])==float(dom_row['raw_count'])+float(trv_row['raw_count'])
    assert read('_domestic_EstIRRCatch_2019_2019.csv')[0]['baseline_start']=='2019'
    assert read('_travel_EstIRRCatch_2019_2019.csv')[0]['baseline_end']=='2019'
    empty=temp/'empty'
    p=subprocess.run(base+['--subgroup','NOT SEROTYPED','--outDir',str(empty)],capture_output=True,text=True)
    assert p.returncode==0,p.stdout+p.stderr
    assert (empty/'SALMONELLA_NOT_SEROTYPED_error.txt').exists()
    assert not list(empty.glob('*_IRCatch.csv'))
    invalid=temp/'invalid'
    p=subprocess.run(base+['--subgroup','Enteritidis','--baseline_start','2025','--baseline_end','2025',
                          '--outDir',str(invalid)],capture_output=True,text=True)
    assert p.returncode!=0 and 'Baseline years unavailable' in p.stderr
print('Actual model flow: travel denominators, baseline exports, empty groups and unavailable baseline passed.')
