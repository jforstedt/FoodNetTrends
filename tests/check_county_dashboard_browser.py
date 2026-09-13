#!/usr/bin/env python3
"""Browser checks for a generated offline dashboard; no datasets in this test."""
import argparse
import csv
import io
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
p=argparse.ArgumentParser();p.add_argument('html',type=Path);p.add_argument('--screenshots',type=Path);a=p.parse_args()
with sync_playwright() as w:
 browser=w.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1100})
 errors=[];requests=[]
 page.on('pageerror',lambda error:errors.append(str(error)));page.on('request',lambda request:requests.append(request.url))
 page.goto(a.html.resolve().as_uri())
 data=json.loads(page.locator('#countyData').text_content())
 assert page.locator('.county-shape').count()==486
 assert not page.locator('#error').is_visible()
 if a.screenshots:
  a.screenshots.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(a.screenshots/'desktop.png'),full_page=True)
 state=data['counties'][-1]['state'];county=next(c for c in data['counties'] if c['state']==state)
 page.select_option('#state',state);page.select_option('#county',county['fips']);page.locator('#year').fill('2004');page.locator('#year').dispatch_event('input')
 assert page.locator('#cases').inner_text()==format(county['rows'][0]['count'],',')
 page.locator('#compare').check();page.locator('#countMode').click();page.select_option('#metric','width')
 assert page.locator('#mapTitle').inner_text()=='Uncertainty: interval width'
 with page.expect_download() as event:page.locator('#download').click()
 download=event.value
 with open(download.path(),newline='') as handle:rows=list(csv.DictReader(handle))
 assert len(rows)==16 and rows[0]['fips']==county['fips'] and int(rows[0]['observed_cases'])==county['rows'][0]['count']
 page.locator('#search').fill('no matching county 000000');assert page.locator('#countyTable tr').count()==0
 page.locator('#search').fill('');page.locator('[data-sort="count"]').click()
 # Map selection works by keyboard, including smaller polygons.
 target=next(c for c in data['counties'] if c['state']==state and c['fips']!=county['fips'])
 page.locator('[data-fips="'+target['fips']+'"]').focus();page.keyboard.press('Enter');assert page.locator('#county').input_value()==target['fips']
 page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(200)
 assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
 assert float(page.locator('#trend').get_attribute('viewBox').split()[2])<=390
 if a.screenshots:page.screenshot(path=str(a.screenshots/'mobile.png'),full_page=True)
 assert not errors,errors
 assert all(url.startswith('file:') for url in requests),requests
 print('PASS desktop/mobile, data values, map keyboard selection, filters, comparison, CSV download, no network requests')
 browser.close()
