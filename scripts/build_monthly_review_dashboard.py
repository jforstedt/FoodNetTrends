#!/usr/bin/env python3
"""Build an offline review of monthly models from verified aggregate archives."""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import tarfile

STATES=('CA','CO','CT','GA','MD','MN','NM','NY','OR','TN')
PATHOGENS=('CAMPYLOBACTER','CRYPTOSPORIDIUM','CYCLOSPORA','LISTERIA','SALMONELLA','SHIGELLA','STEC','VIBRIO','YERSINIA')
sha=lambda b:hashlib.sha256(b).hexdigest()

def read_archive(path):
 path=Path(path);data={};total=0
 with tarfile.open(str(path)) as archive:
  for m in archive.getmembers():
   if not m.isfile():continue
   if m.name in data or m.name.startswith('/') or '..' in Path(m.name).parts:raise ValueError('Unsafe or duplicate archive member')
   total+=m.size
   if m.size>128*1024*1024 or total>1024*1024*1024:raise ValueError('Archive exceeds report size limit')
   data[m.name]=archive.extractfile(m).read()
 manifest=json.loads(data['report_sha256.json'])
 if not manifest or any(n not in data or sha(data[n])!=h for n,h in manifest.items()):raise ValueError('Archive manifest differs')
 # Every consumed report must be covered, not merely the files listed by a partial manifest.
 for n in data:
  if n!='report_sha256.json' and n not in manifest:raise ValueError('Unmanifested archive member: '+n)
 return data,sha(path.read_bytes())

def table(data,name):return list(csv.DictReader(io.StringIO(data[name].decode('utf-8'))))
def finite(r,key):
 x=float(r[key])
 if not math.isfinite(x):raise ValueError('Nonfinite '+key)
 return x

def task_result(data,t,plan_name):
 name=t['id'];record=json.loads(data[name+'/task_status.json'])
 if record.get('status')!='COMPLETE':return None
 if record.get('task')!=name or record.get('exit_status')!=0 or record.get('plan_sha256')!=sha(data[plan_name]):raise ValueError('Task identity mismatch')
 for f,h in record.get('outputs',{}).items():
  if name+'/'+f in data and sha(data[name+'/'+f])!=h:raise ValueError('Task output changed')
 for f in ('aggregate_tails.csv','stream_scores.csv','settings.csv'):
  if record.get('outputs',{}).get('result/'+f)!=sha(data[name+'/result/'+f]):raise ValueError('Unbound task report')
 settings=table(data,name+'/result/settings.csv')
 if len(settings)!=1 or settings[0]['seasonal']!='TRUE' or int(settings[0]['cutoff'])!=t['cutoff'] or settings[0]['coverage_certified']!='FALSE' or int(settings[0]['streams'])!=4 or int(settings[0]['draws_per_stream'])!=2000:raise ValueError('Unexpected sampling settings')
 tails=table(data,name+'/result/aggregate_tails.csv');scores=table(data,name+'/result/stream_scores.csv')
 for rr,states in ((tails,STATES+('ALL',)),(scores,STATES)):
  keys={(r['state'],int(r['year']),int(r['stream'])) for r in rr}
  expected={(s,y,k) for s in states for y in range(t['cutoff']+1,t['cutoff']+4) for k in range(5)}
  if len(rr)!=len(expected) or keys!=expected:raise ValueError('Incomplete forecast domain')
  if any(int(r['draws'])!=(8000 if r['stream']=='0' else 2000) for r in rr):raise ValueError('Unexpected posterior draw count')
 result=[]
 for r in tails:
  if r['stream']!='0':continue
  z={k:finite(r,k) for k in ('observed','mean_expected','median_expected','lower95','median_predictive','upper95')}
  if min(z.values())<0 or z['observed']!=int(z['observed']) or not z['lower95']<=z['median_predictive']<=z['upper95']:raise ValueError('Invalid count/interval')
  ss=[x for x in scores if x['stream']=='0' and x['year']==r['year'] and (r['state']=='ALL' or x['state']==r['state'])]
  z.update(state=r['state'],year=int(r['year']),score=sum(finite(x,'mean_log_score') for x in ss)/len(ss))
  result.append(z)
 return result

def build(paths,decisions):
 expected=decisions['archives'];runs=[];provenance=[]
 if set(decisions['pathogens'])!=set(PATHOGENS):raise ValueError('Incomplete pathogen assessment')
 for pathogen,d in decisions['pathogens'].items():
  if d['candidate'] not in ('ar1','rw1',None):raise ValueError('Invalid candidate')
 for path in paths:
  data,digest=read_archive(path)
  if expected.get(Path(path).name)!=digest:raise ValueError('Archive differs from reviewed assessment')
  provenance.append(dict(archive=Path(path).name,sha256=digest))
  pn='expansion.json' if 'expansion.json' in data else 'plan.json';plan=json.loads(data[pn]);version=plan['version']
  if version not in ('saved_monthly_diagnostics_v1','monthly_ar1_comparison_v1','monthly_expansion_v1'):raise ValueError('Unsupported comparison archive')
  for t in plan['tasks']:
   if not t['seasonal']:continue
   model=t.get('temporal','ar1' if version=='monthly_ar1_comparison_v1' else 'rw1')
   rr=task_result(data,t,pn)
   if rr is not None:runs.append(dict(pathogen=t['pathogen'],origin=t['cutoff'],model=model,rows=rr,archive=Path(path).name))
 if len(provenance)!=len(expected) or {x['archive'] for x in provenance}!=set(expected):raise ValueError('Assessment archive set differs')
 keys={(r['pathogen'],r['origin'],r['model']) for r in runs}
 wanted={(p,c,m) for p in PATHOGENS for c in ((2011,2013,2014) if p=='CRYPTOSPORIDIUM' else (2011,2013,2016)) for m in ('rw1','ar1')}
 if len(runs)!=54 or keys!=wanted:raise ValueError('Incomplete or duplicate nine-pathogen comparison')
 idx={(r['pathogen'],r['origin'],r['model']):r for r in runs}
 for p,c,m in keys:
  left=idx[p,c,m]['rows'];right=idx[p,c,'ar1' if m=='rw1' else 'rw1']['rows']
  if {(r['state'],r['year']):r['observed'] for r in left}!={(r['state'],r['year']):r['observed'] for r in right}:raise ValueError('Paired observed totals differ')
 return dict(runs=runs,assessments=decisions['pathogens'],provenance=provenance,assessment_sha256=sha(json.dumps(decisions,sort_keys=True).encode()),coverage_certified=False)

def render(payload,template):
 if template.count('__MONTHLY_DATA__')!=1:raise ValueError('Invalid template')
 return template.replace('__MONTHLY_DATA__',json.dumps(payload,allow_nan=False,separators=(',',':')).replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e'))

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',action='append',required=True);p.add_argument('--decisions',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():p.error('Refusing existing output')
 payload=build(a.archive,json.loads(a.decisions.read_text()));html=render(payload,(Path(__file__).resolve().parents[1]/'dashboard/monthly_review_template.html').read_text())
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(html);print('Offline review: '+str(a.output));return 0
if __name__=='__main__':main()
