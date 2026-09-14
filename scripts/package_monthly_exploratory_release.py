#!/usr/bin/env python3
"""Package the bounded internal monthly-model review; no fitting or promotion."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipfile
import build_monthly_review_dashboard as review

README='''# FoodNet exploratory monthly-model review

Open dashboard.html in a current browser. No server, installation, network connection or cluster access is required.

## What this package contains

- Nine-pathogen seasonal RW1 versus AR1 comparisons at three historical origins: 54 fitted model/origin combinations.
- Annual forecast totals from monthly models, observed totals, joint predictive intervals and downloadable comparison tables.
- Raw-record diagnostic-category descriptions, field completeness and literal-code crosswalks when supplied.
- model_status.csv, reviewed assessment, source/input provenance and file integrity hashes.

## What it does not establish

This is an INTERNAL EXPLORATORY REVIEW, not a validated forecasting service. The historical periods informed development. No independent final-validation period is established in the current audited monthly data. Model labels are provisional candidates for validation, not production acceptance. Consult model_status.csv for pathogens unsupported for general forecasting under either tested approach.

Monthly surveillance continuity is assumed, not certified. Retrospective forecasts use realized future population exposure. Cryptosporidium ends in 2017. Coverage percentages on overlapping origins and sites are descriptive, not independent calibration trials. Some individual predictive tail scores have substantial Monte Carlo uncertainty.

The charts summarize monthly-model predictions into annual totals; monthly curves, live forecasts, reporting-delay nowcasts and testing-adjusted incidence are not included. Diagnostic descriptions concern the raw case-record universe, not the eligible model population or everyone tested. CX+ must not be interpreted as culture-only. Do not use diagnostic shares as an estimate of testing intensity or a causal correction.

Daniel's accepted annual/state model and dashboard remain separate and unchanged. This package does not replace them, merge their uncertainty with county estimates or alter case eligibility. Additional predictors and spline combinations are later work.

## Use and handling

Start with the nine-pathogen assessment, then select a pathogen, training cutoff and geography. Compare observed totals with both forecast intervals and point estimates. Higher county/month predictive log scores are better; the catchment score averages sites equally and is not a probability score of the catchment total. Wide intervals alone do not prove accuracy.

This HTML embeds internal aggregate study data. Keep this package internal; it is not automatically published. No individual records, laboratory identifiers or saved fit objects are included. SHA256SUMS.json binds the packaged files; provenance.json identifies source archives and builder sources. Source hashes establish identity, not scientific validity.
'''

def package(archives,decisions,diagnostics,destination):
 destination=Path(destination).resolve();zip_path=Path(str(destination)+'.zip')
 if destination.exists() or zip_path.exists():raise ValueError('Refusing existing release directory or ZIP')
 assessment=json.loads(Path(decisions).read_text());payload=review.build(archives,assessment,diagnostics)
 root=Path(__file__).resolve().parents[1];template=root/'dashboard/monthly_review_template.html'
 html=review.render(payload,template.read_text())
 destination.parent.mkdir(parents=True,exist_ok=True)
 stage=Path(tempfile.mkdtemp(prefix='.monthly-release-',dir=str(destination.parent)))
 created_zip=False
 try:
  (stage/'dashboard.html').write_text(html);(stage/'README.md').write_text(README)
  (stage/'assessment.json').write_text(json.dumps(assessment,indent=2)+'\n')
  with (stage/'model_status.csv').open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=['pathogen','candidate','status','limitation']);w.writeheader()
   for p,a in sorted(payload['assessments'].items()):w.writerow(dict(pathogen=p,candidate=a['candidate'] or '',status='CANDIDATE_FOR_VALIDATION' if a['candidate'] else 'UNSUPPORTED_FOR_GENERAL_FORECASTING',limitation=a['limitation']))
  sources=['scripts/package_monthly_exploratory_release.py','scripts/build_monthly_review_dashboard.py','scripts/monthly_diagnostic_view.py','dashboard/monthly_review_template.html']
  provenance=dict(package_type='INTERNAL_EXPLORATORY_REVIEW',models=54,pathogens=9,accepted=False,coverage_certified=False,refitted=False,archives=payload['provenance'],diagnostic_archive=None if not payload.get('diagnostics') else dict(archive=payload['diagnostics']['archive'],sha256=payload['diagnostics']['sha256']),source_sha256={n:review.sha((root/n).read_bytes()) for n in sources})
  (stage/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
  hashes={p.name:review.sha(p.read_bytes()) for p in stage.iterdir()}
  (stage/'SHA256SUMS.json').write_text(json.dumps(hashes,indent=2)+'\n')
  with zipfile.ZipFile(zip_path,'x',compression=zipfile.ZIP_DEFLATED) as z:
   created_zip=True
   for p in sorted(stage.iterdir()):z.write(p,arcname=p.name)
  verify_zip(zip_path)
  if destination.exists():raise ValueError('Release destination appeared during build')
  stage.rename(destination)
 except Exception:
  shutil.rmtree(str(stage),ignore_errors=True)
  if created_zip and zip_path.exists():zip_path.unlink()
  raise
 return zip_path

def verify_zip(path):
 with zipfile.ZipFile(path) as z:
  names=z.namelist()
  expected={'README.md','dashboard.html','assessment.json','model_status.csv','provenance.json','SHA256SUMS.json'}
  if len(names)!=len(expected) or set(names)!=expected:raise ValueError('Unexpected package members')
  hashes=json.loads(z.read('SHA256SUMS.json'))
  if set(hashes)!=expected-{'SHA256SUMS.json'} or any(review.sha(z.read(n))!=h for n,h in hashes.items()):raise ValueError('Release integrity check failed')
 return True

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',action='append',required=True);p.add_argument('--decisions',required=True,type=Path);p.add_argument('--diagnostics',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
 print('Internal release ZIP: '+str(package(a.archive,a.decisions,a.diagnostics,a.output)));return 0
if __name__=='__main__':main()
