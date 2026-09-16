"""Independent direct-raw versus affine-rebase scientific checks."""
import copy
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import prepare_covariate_factorial as direct
import rebase_covariate_features as rebased


def fixture():
    weather=[]; ages=[]
    for i,f in enumerate(('01001','01003')):
        for y in range(2003,2020):
            for m in range(1,13):
                weather.append(dict(fips=f,year=str(y),month=str(m),
                    tavg_c=str(5*i + 2*m + .17*(y-2004)**2 + math.sin(m+y)),
                    prcp_mm=str(30+3*i+2*m+.3*(y-2003)**2)))
            ages.append(dict(fips=f,year=str(y),under5_share=str(.04+.005*i+.0004*(y-2003)),
                             age65plus_share=str(.11+.025*i+.0003*(y-2003)**1.3)))
    return weather,ages


class RebaseTests(unittest.TestCase):
    def assert_features_equal(self, left, right, training_only=False):
        def indexed(rows):
            return {(r['fips'],int(r['year']),int(r['month'])):r for r in rows if not training_only or int(r['year'])<=2014}
        left=indexed(left); right=indexed(right)
        self.assertEqual(set(left),set(right))
        for key in left:
            for field in rebased.FEATURES:
                self.assertAlmostEqual(left[key][field],right[key][field],places=10,msg=str((key,field)))

    def test_equivalence_to_direct_2014_both_windows_and_no_mutation(self):
        weather,ages=fixture()
        for window in ('current','lag01'):
            with self.subTest(window=window):
                src,_=direct.transform(weather,ages,2016,window,counties=2)
                before=copy.deepcopy(src)
                expected,_=direct.transform(weather,ages,2014,window,counties=2)
                actual,parameters=rebased.rebase(src,2014,2016,counties=2)
                self.assert_features_equal(actual,expected)
                self.assertEqual(src,before)
                self.assertEqual(len(actual),2*14*12)
                for field in rebased.FEATURES:
                    groups=parameters[field]['centers_in_source_units']
                    self.assertEqual(len(groups),24 if field.startswith('weather_') else 1)
                    values=[r[field] for r in actual if r['year']<=2014]
                    self.assertAlmostEqual(math.fsum(values)/len(values),0,places=12)
                    self.assertAlmostEqual(math.fsum(x*x for x in values)/len(values),1,places=12)

    def test_changed_future_raw_data_cannot_leak_into_earlier_training(self):
        weather,ages=fixture()
        for window in ('current','lag01'):
            src,contract=direct.transform(weather,ages,2016,window,counties=2)
            baseline,_=rebased.rebase(src,2014,2016,counties=2)
            changed_weather=copy.deepcopy(weather); changed_ages=copy.deepcopy(ages)
            for row in changed_weather:
                if int(row['year'])>2014: row.update(tavg_c='135.5',prcp_mm='2391')
            for row in changed_ages:
                if int(row['year'])>2014: row.update(under5_share='.25',age65plus_share='.35')
            changed,changed_contract=direct.transform(changed_weather,changed_ages,2016,window,counties=2)
            self.assertNotEqual(contract['scales'],changed_contract['scales'])
            self.assertNotEqual(contract['age_centers'],changed_contract['age_centers'])
            actual,_=rebased.rebase(changed,2014,2016,counties=2)
            self.assert_features_equal(actual,baseline,training_only=True)
            expected,_=direct.transform(changed_weather,changed_ages,2014,window,counties=2)
            self.assert_features_equal(actual,expected)

    def test_missing_county_month_and_wrong_footprint_rejected(self):
        src,_=direct.transform(*fixture(),2016,'current',counties=2)
        with self.assertRaisesRegex(ValueError,'Incomplete'): rebased.rebase(src[1:],2014,2016,counties=2)
        with self.assertRaisesRegex(ValueError,'Incomplete'): rebased.rebase(src,2014,2016,counties=3)
        with self.assertRaisesRegex(ValueError,'Incomplete'): rebased.rebase([r for r in src if r['fips']=='01001'],2014,2016,counties=2)

    def test_duplicate_nonfinite_invalid_keys_and_constant_features_rejected(self):
        src,_=direct.transform(*fixture(),2016,'current',counties=2)
        with self.assertRaisesRegex(ValueError,'Duplicate'): rebased.rebase(src+[src[0]],2014,2016,counties=2)
        for value in ('nan','inf','-inf'):
            bad=copy.deepcopy(src);bad[0]['age_under5_z']=value
            with self.assertRaisesRegex(ValueError,'Nonfinite'): rebased.rebase(bad,2014,2016,counties=2)
        for field,value in [('fips','1001'),('month',13)]:
            bad=copy.deepcopy(src);bad[0][field]=value
            with self.assertRaisesRegex(ValueError,'Invalid key'): rebased.rebase(bad,2014,2016,counties=2)
        bad=copy.deepcopy(src)
        for row in bad: row['age_under5_z']=1
        with self.assertRaisesRegex(ValueError,'scale'): rebased.rebase(bad,2014,2016,counties=2)
        for cutoff,source in [(2016,2016),(2017,2016),(2004,2016)]:
            with self.assertRaisesRegex(ValueError,'Earlier'): rebased.rebase(src,cutoff,source,counties=2)

    def test_prepare_binds_source_and_replaces_obsolete_parameters(self):
        rows,manifest=direct.transform(*fixture(),2016,'current',counties=2)
        buf=io.StringIO();writer=csv.DictWriter(buf,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        payload=buf.getvalue().encode()
        manifest['outputs']={'features.csv':hashlib.sha256(payload).hexdigest()}
        original_rebase=rebased.rebase
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=root/'features.csv';mp=root/'manifest.json'
            src.write_bytes(payload);mp.write_text(json.dumps(manifest))
            with mock.patch.object(rebased,'rebase',side_effect=lambda rows,cutoff,source:original_rebase(rows,cutoff,source,counties=2)):
                result=rebased.prepare(src,mp,2014,root/'out')
            self.assertEqual(result['training_cutoff_year'],2014)
            self.assertEqual(result['forecast_years'],[2015,2016,2017])
            for name in ('centers','scales','age_centers','age_scales'): self.assertNotIn(name,result)
            self.assertEqual(result['rebase_source']['manifest_sha256'],hashlib.sha256(mp.read_bytes()).hexdigest())
            self.assertEqual(result['outputs']['weather_experiment.csv'],hashlib.sha256((root/'out/weather_experiment.csv').read_bytes()).hexdigest())
            src.write_bytes(payload+b'\n')
            with self.assertRaisesRegex(ValueError,'changed source'): rebased.prepare(src,mp,2014,root/'bad')
            self.assertFalse((root/'bad').exists())

if __name__=='__main__': unittest.main()
