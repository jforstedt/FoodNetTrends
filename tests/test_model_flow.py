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
    # A 2025 parasite case must be explicitly excluded by default, not silently
    # lost in a population join. Raising the limit without populations must fail.
    parasite_cases = temp/'parasites.csv'
    parasite_rows = []
    for year in range(2010,2026):
        row = dict(rows[0], pathogen='CYCLOSPORA', state='CA', county='ALAMEDA', year=str(year), cxcidt='PARASITIC')
        parasite_rows.append(row)
    with parasite_cases.open('w') as handle:
        writer=csv.DictWriter(handle,fields); writer.writeheader(); writer.writerows(parasite_rows)
    pop = temp/'parasite_pop.csv'
    with pop.open('w') as handle:
        writer=csv.DictWriter(handle,['year','state','population']); writer.writeheader()
        writer.writerows(dict(year=y,state='CA',population=100000) for y in range(2010,2025))
    pbase = base + ['--pathogen','CYCLOSPORA','--subgroup','combined','--states','CA',
                    '--cleanFile',str(parasite_cases),'--censusFileP',str(pop)]
    limited=temp/'limited'
    p=subprocess.run(pbase+['--outDir',str(limited)],capture_output=True,text=True)
    assert p.returncode==0 and not list(limited.glob('*_error.txt')),p.stdout+p.stderr
    with (limited/'CYCLOSPORA_combined_IRCatch.csv').open() as handle:
        assert max(int(r['year']) for r in csv.DictReader(handle))==2024
    with (limited/'CYCLOSPORA_combined_input_exclusions.csv').open() as handle:
        assert any(r['year']=='2025' and r['records']=='1' for r in csv.DictReader(handle))
    p=subprocess.run(pbase+['--parasite_end_year','2025','--outDir',str(temp/'missing2025')],capture_output=True,text=True)
    assert p.returncode!=0 and 'Missing Parasitic population years: 2025' in p.stderr,p.stdout+p.stderr
print('Actual model flow: travel denominators, baseline exports, empty groups and unavailable baseline passed.')
