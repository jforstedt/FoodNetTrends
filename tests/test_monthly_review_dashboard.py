import csv
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_monthly_review_dashboard as m
class DashboardTests(unittest.TestCase):
 def test_manifest_tampering_and_omission(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'report.tar.gz'
   def write(manifest,extra=False):
    data={'result.txt':b'valid','report_sha256.json':json.dumps(manifest).encode()}
    if extra:data['unbound.csv']=b'extra'
    with tarfile.open(p,'w:gz') as t:
     for n,b in data.items():z=tarfile.TarInfo(n);z.size=len(b);t.addfile(z,io.BytesIO(b))
   write({'result.txt':m.sha(b'valid')});m.read_archive(p)
   write({'result.txt':m.sha(b'changed')})
   with self.assertRaisesRegex(ValueError,'manifest'):m.read_archive(p)
   write({'result.txt':m.sha(b'valid')},True)
   with self.assertRaisesRegex(ValueError,'Unmanifested'):m.read_archive(p)
 def test_safe_json_embedding(self):
  s=m.render({'x':'</script><img onerror=alert(1)>'},'<script>__MONTHLY_DATA__</script>')
  self.assertEqual(s.count('</script>'),1);self.assertIn('\\u003c',s)
 def test_task_domain_and_interval(self):
  def b(rows):
   f=io.StringIO();w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows);return f.getvalue().encode()
  task=dict(id='TEST',cutoff=2011);d={'plan.json':b'{}'}
  scores=[dict(state=s,year=y,stream=k,draws=8000 if k==0 else 2000,mean_log_score=-1) for s in m.STATES for y in (2012,2013,2014) for k in range(5)]
  tails=[dict(state=s,year=y,stream=k,draws=8000 if k==0 else 2000,observed=10,mean_expected=11,median_expected=10,lower95=2,median_predictive=10,upper95=20) for s in m.STATES+('ALL',) for y in (2012,2013,2014) for k in range(5)]
  settings=[dict(seasonal='TRUE',cutoff=2011,coverage_certified='FALSE',streams=4,draws_per_stream=2000)]
  def bind():
   for n,rr in [('aggregate_tails.csv',tails),('stream_scores.csv',scores),('settings.csv',settings)]:d['TEST/result/'+n]=b(rr)
   d['TEST/task_status.json']=json.dumps(dict(status='COMPLETE',task='TEST',exit_status=0,plan_sha256=m.sha(d['plan.json']),outputs={n.removeprefix('TEST/'):m.sha(v) for n,v in d.items() if n.startswith('TEST/result/')})).encode()
  bind();self.assertEqual(len(m.task_result(d,task,'plan.json')),33)
  tails[0]['lower95']=30;bind()
  with self.assertRaisesRegex(ValueError,'interval'):m.task_result(d,task,'plan.json')
  tails.pop();bind()
  with self.assertRaisesRegex(ValueError,'domain'):m.task_result(d,task,'plan.json')
if __name__=='__main__':unittest.main()
