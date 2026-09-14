#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

def main():
 p=argparse.ArgumentParser();p.add_argument('html',type=Path);a=p.parse_args()
 with sync_playwright() as w:
  browser=w.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1300,'height':950});errors=[];requests=[]
  page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:requests.append(r.url));page.goto(a.html.resolve().as_uri())
  data=json.loads(page.locator('#monthlyData').text_content());assert len(data['runs'])==54
  assert page.locator('#overview tr').count()==9
  for pathogen in data['assessments']:
   page.select_option('#pathogen',pathogen)
   for origin in sorted({r['origin'] for r in data['runs'] if r['pathogen']==pathogen}):
    page.select_option('#origin',str(origin));assert page.locator('#results tr').count()==6
   expected='Neither' if data['assessments'][pathogen]['candidate'] is None else 'candidate for validation'
   assert expected in page.locator('#status').inner_text()
  page.select_option('#state','GA');assert page.locator('#results tr').count()==6
  with page.expect_download() as event:page.locator('#download').click()
  with open(event.value.path(),newline='') as f:rows=list(csv.DictReader(f))
  assert len(rows)==6 and all(r['state']=='GA' and r['status']=='EXPLORATORY_ASSUMED_CONTINUOUS' for r in rows)
  if data.get('diagnostics'):
   assert page.locator('#diagnosticsSection').is_visible()
   for pathogen in data['assessments']:
    page.select_option('#diagPathogen',pathogen)
    assert page.locator('#completeness tr').count()>0
   page.select_option('#diagPathogen','SALMONELLA');page.select_option('#diagState','GA');page.select_option('#diagField','pcrclinic')
   assert 'CX+CIDT+' in page.locator('#crosswalk').inner_text()
   with page.expect_download() as event:page.locator('#diagDownload').click()
   with open(event.value.path(),newline='') as f:raw=list(csv.DictReader(f))
   expected=[r for r in data['diagnostics']['codes'] if r[0]=='SALMONELLA' and r[1]=='GA' and r[3]=='pcrclinic']
   assert len(raw)==len(expected) and sum(int(r['records']) for r in raw)==sum(r[5] for r in expected)
   assert all(r['universe']=='RAW_RECORDS_NOT_MODEL_ELIGIBILITY' for r in raw)
  page.set_viewport_size({'width':390,'height':844});assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
  assert not errors,errors;assert all(u.startswith('file:') for u in requests),requests
  print('PASS all 54 selections, nine assessments, CSV, mobile layout, no browser errors or external requests');browser.close()
if __name__=='__main__':main()
