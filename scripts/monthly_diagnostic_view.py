"""Derive raw-universe descriptive views; never adjust incidence or infer testing."""
import csv
import hashlib
import io
import json
import math
import tarfile
from pathlib import Path
from collections import defaultdict

sha=lambda b:hashlib.sha256(b).hexdigest()

def derive(codes,dates,crosswalk):
 def count(r):
  n=float(r['records'])
  if not math.isfinite(n) or n<0 or n!=int(n):raise ValueError('Invalid record count')
  return int(n)
 def key(r):return (r['pathogen'],r['state'],int(r['year']))
 totals={}
 for r in dates:
  k=key(r)
  if k in totals:raise ValueError('Duplicate raw denominator')
  totals[k]=count(r)
 fields=sorted({r['field'] for r in codes});seen=set();sums=defaultdict(int);out=[];classification={}
 for r in codes:
  k=key(r);identity=k+(r['field'],r['code'])
  if identity in seen:raise ValueError('Duplicate literal code')
  seen.add(identity);n=count(r);sums[k+(r['field'],)]+=n
  out.append([*k,r['field'],r['code'],n])
  if r['field']=='cxcidt':classification[k+(r['code'],)]=n
 if not fields or set(sums)!={k+(f,) for k in totals for f in fields} or any(n!=totals[k[:3]] for k,n in sums.items()):raise ValueError('Field totals do not reconcile to raw records')
 seen=set();cross=[];cs=defaultdict(int)
 for r in crosswalk:
  if r['field']!='culturestatus':continue
  k=key(r);identity=k+(r['category'],r['result_code'])
  if identity in seen:raise ValueError('Duplicate crosswalk row')
  seen.add(identity);n=count(r);cs[k+(r['category'],)]+=n;cross.append([*k,r['category'],r['result_code'],n])
 if dict(cs)!=classification:raise ValueError('Crosswalk does not reconcile to classification')
 return dict(codes=out,crosswalk=cross,fields=fields,universe='RAW_RECORDS_NOT_MODEL_ELIGIBILITY',columns=['pathogen','state','year','field','literal_code','records'])

def load(path,expected_sha):
 path=Path(path)
 if sha(path.read_bytes())!=expected_sha:raise ValueError('Diagnostic archive differs from review')
 needed=['definitions/task_status.json']
 data={}
 with tarfile.open(str(path)) as t:
  members={}
  for m in t.getmembers():
   if m.name in members:raise ValueError('Duplicate archive member')
   members[m.name]=m
  record=json.loads(t.extractfile(members[needed[0]]).read())
  if record.get('task')!='definitions' or record.get('status')!='COMPLETE' or record.get('exit_status')!=0:raise ValueError('Definition audit incomplete')
  for f,h in record.get('outputs',{}).items():
   name='definitions/'+f;m=members[name]
   if not m.isfile() or m.size>128*1024*1024:raise ValueError('Invalid definition report')
   b=t.extractfile(m).read()
   if sha(b)!=h:raise ValueError('Definition report changed')
   data[f]=b
 def rows(n):return list(csv.DictReader(io.StringIO(data['result/'+n].decode())))
 result=derive(rows('test_codes.csv'),rows('date_checks.csv'),rows('category_test_crosswalk.csv'))
 result.update(archive=path.name,sha256=expected_sha,verified_reports=len(data))
 return result
