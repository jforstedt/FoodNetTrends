import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('covariate_join', Path(__file__).resolve().parents[1] / 'scripts/join_county_covariates.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class JoinTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        self.ref = [dict(fips='01001', year='2019', month='1', cases='003', population='100.00'),
                    dict(fips='01003', year='2019', month='1', cases='', population='200.00'),
                    dict(fips='01001', year='2020', month='1', cases='999', population='101.00')]
        self.weather = [dict(fips=r['fips'], year=r['year'], month=r['month'], tavg_c=str(x), prcp_mm=str(x+10)) for r,x in zip(self.ref,[1,3,100])]
        self.ages = [dict(fips=r['fips'], year=r['year'], under5_share=str(x), age65plus_share=str(x+0.1)) for r,x in zip(self.ref,[0.05,0.07,0.4])]

    def write(self, name, rows, bind=False):
        p=self.d/name
        with p.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
        if bind:
            (self.d/(name+'.json')).write_text(json.dumps(dict(schema='county_covariate_source_v1',source_url='https://example.org/public.csv',retrieved_at='2026-09-15',files={name:hashlib.sha256(p.read_bytes()).hexdigest()})))
        return p

    def run_join(self, mode='historical_conditional'):
        self.write('ref.csv',self.ref);self.write('weather.csv',self.weather,True);self.write('ages.csv',self.ages,True)
        return m.assemble(self.d/'ref.csv',self.d/'weather.csv',self.d/'ages.csv',self.d/'weather.csv.json',self.d/'ages.csv.json','2019-12',mode)

    def test_preserves_domain_outcomes_and_training_transform(self):
        _, out, meta=self.run_join()
        self.assertEqual([{k:r[k] for k in self.ref[0]} for r in out],self.ref)
        self.assertEqual(meta['standardization']['tavg_c'],dict(mean=2.0,sd_population=1.0))
        self.assertEqual(out[2]['tavg_c_z'],98.0)
        self.weather[2]['tavg_c']='2000';self.ref[0]['cases']='50000'
        _,_,changed=self.run_join()
        self.assertEqual(changed['standardization'],meta['standardization'])

    def test_rejects_missing_duplicate_and_conflicts(self):
        self.weather.pop()
        with self.assertRaisesRegex(ValueError,'Missing covariate support'):self.run_join()
        self.setUp();self.weather.append(dict(self.weather[0]))
        with self.assertRaisesRegex(ValueError,'Duplicate covariate'):self.run_join()
        self.setUp();self.ref.append(dict(self.ref[0]))
        with self.assertRaisesRegex(ValueError,'Duplicate reference'):self.run_join()
        self.setUp()
        for r in self.ref:r['tavg_c']='44'
        with self.assertRaisesRegex(ValueError,'conflicts'):self.run_join()

    def test_rejects_unbound_payload_and_operational_mode(self):
        self.run_join()
        p=self.d/'weather.csv';p.write_text(p.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'SHA256 mismatch'):
            m.read_bound(p,self.d/'weather.csv.json')
        with self.assertRaisesRegex(ValueError,'Only historical_conditional'):self.run_join('operational_forecast')

    def test_invalid_shares_missing_values_and_constant_training(self):
        for bad in ('nan','','inf'):
            self.weather[0]['tavg_c']=bad
            with self.assertRaises(ValueError):self.run_join()
        self.setUp();self.ages[0]['under5_share']='0.9'
        with self.assertRaisesRegex(ValueError,'exceed one'):self.run_join()
        self.setUp();self.weather[1]['tavg_c']='1'
        with self.assertRaisesRegex(ValueError,'Constant'):self.run_join()

    def test_native_manifests_and_duplicate_json_keys(self):
        self.run_join()
        wp=self.d/'weather.csv';ap=self.write('county_age_shares.csv',self.ages)
        wm=dict(version='county_weather_v1',mode='historical_conditional',forecast_asof_validated=False,
                units=dict(tavg_c='degrees_C_daily_mean',prcp_mm='mm_monthly_sum'),
                sources={'raw.csv':dict(url='https://example.org/raw.csv',sha256='a'*64)},
                outputs={wp.name:hashlib.sha256(wp.read_bytes()).hexdigest()})
        am=dict(schema_version='county_age_covariates_v1',retrospective_vintages=True,
                forecast_asof_validated=False,population_offset_replaced=False,case_data_used=False,
                inputs={'raw.csv':'b'*64},source_urls=['https://example.org/raw.csv'],
                output_sha256=hashlib.sha256(ap.read_bytes()).hexdigest())
        (self.d/'wm.json').write_text(json.dumps(wm));(self.d/'am.json').write_text(json.dumps(am))
        _,out,meta=m.assemble(self.d/'ref.csv',wp,ap,self.d/'wm.json',self.d/'am.json','2019-12','historical_conditional')
        self.assertEqual(len(out),3)
        self.assertFalse(meta['ages']['upstream_raw_hashes_rechecked_here'])
        (self.d/'wm.json').write_text('{"version":"x","version":"y"}')
        with self.assertRaisesRegex(ValueError,'Duplicate manifest JSON'):m.read_bound(wp,self.d/'wm.json')

    def test_fips_and_no_training_fail(self):
        self.ref[0]['fips']='1001'
        with self.assertRaisesRegex(ValueError,'five digits'):self.run_join()
        self.setUp();self.run_join()
        with self.assertRaisesRegex(ValueError,'training rows'):
            m.assemble(self.d/'ref.csv',self.d/'weather.csv',self.d/'ages.csv',self.d/'weather.csv.json',self.d/'ages.csv.json','2018-12','historical_conditional')


if __name__=='__main__':unittest.main()
