import csv, importlib.util, os, subprocess, tarfile, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('pilot',ROOT/'scripts/launch_county_pilot_audit.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
with tempfile.TemporaryDirectory(prefix="pilot ' space ") as d:
 p=Path(d);dest=p/'job';cmd=m.prepare(ROOT,dest,p/'clean file.csv',p/'population.sas7bdat')
 assert cmd[cmd.index('-pe')+1:cmd.index('-pe')+3]==['smp','1']
 (dest/'county_panel_INTERNAL.rds').write_text('must not be archived')
 b=p/'bin';b.mkdir();s=b/'singularity';s.write_text('#!/bin/bash\necho diagnostic failure\nexit 7\n');s.chmod(0o755)
 r=subprocess.run(['bash',str(dest/'run.sh')],env=dict(os.environ,PATH=str(b)+':'+os.environ['PATH']),stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
 assert r.returncode==7,(r.stdout,r.stderr)
 with tarfile.open(str(dest)+'.tar.gz') as t:
  assert not any('county_panel' in n for n in t.getnames())
  assert b'diagnostic failure' in t.extractfile('reports/audit.log').read()
rows=list(csv.DictReader((ROOT/'analysis_configs/county_pilot/counties.csv').open()))
assert len(rows)==486 and len({r['fips'] for r in rows})==486
assert next(r['county'] for r in rows if r['fips']=='27111')=='Otter Tail County'
assert next(r['county'] for r in rows if r['fips']=='27153')=='Todd County'
edges=list(csv.DictReader((ROOT/'analysis_configs/county_pilot/edges.csv').open()));ids={r['fips'] for r in rows}
assert all(e['fips_a'] in ids and e['fips_b'] in ids and e['fips_a']<e['fips_b'] for e in edges)
print('PASS pilot footprint, source label resolution, launcher failure archive, and exact-panel exclusion')
