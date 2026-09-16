import importlib.util
import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import prepare_weather_experiment as m


def fixture():
    return [dict(fips=f,year=str(y),month=str(month),tavg_c=str(month+(y-2004)*2+i),prcp_mm=str(10+month+(y-2004)*3+i),cases='neverread')
            for i,f in enumerate(['01001','01003']) for y in range(2004,2009) for month in range(1,13)]


class WeatherTests(unittest.TestCase):
    def test_anomalies_training_zero_mean_unit_scale_and_source_unchanged(self):
        rows=fixture();original=[dict(r) for r in rows];out,c=m.build(rows,2005,2)
        self.assertEqual(rows,original);self.assertEqual(len(out),120)
        for feature in c['feature_order']:
            train=[r[feature] for r in out if r['year']<=2005]
            self.assertAlmostEqual(sum(train)/len(train),0)
            self.assertAlmostEqual(sum(z*z for z in train)/len(train),1)
            for f in ['01001','01003']:
                for month in range(1,13):
                    self.assertAlmostEqual(sum(r[feature] for r in out if r['year']<=2005 and r['fips']==f and r['month']==month),0)

    def test_future_and_outcomes_do_not_change_fit(self):
        rows=fixture();_,a=m.build(rows,2005,2)
        for r in rows:
            r['cases']='1000000'
            if int(r['year'])>2005:r.update(tavg_c='999',prcp_mm='9999')
        out,b=m.build(rows,2005,2)
        self.assertEqual(a['centers'],b['centers']);self.assertEqual(a['scales'],b['scales'])
        self.assertTrue(all(math.isfinite(r['weather_logprcp_z']) for r in out))

    def test_missing_duplicate_bad_weather(self):
        rows=fixture();rows.pop()
        with self.assertRaisesRegex(ValueError,'Incomplete'):m.build(rows,2005,2)
        rows=fixture();rows.append(dict(rows[0]))
        with self.assertRaisesRegex(ValueError,'Duplicate'):m.build(rows,2005,2)
        for bad in ['nan','-1','']:
            rows=fixture();rows[0]['prcp_mm']=bad
            with self.assertRaises(ValueError):m.build(rows,2005,2)

    def test_constant_training_and_footprint_rejected(self):
        rows=fixture()
        for r in rows:r['tavg_c']=r['month']
        with self.assertRaisesRegex(ValueError,'scale'):m.build(rows,2005,2)
        with self.assertRaisesRegex(ValueError,'footprint'):m.build(fixture(),2005)

    def test_logprecip_before_county_month_centering(self):
        out,c=m.build(fixture(),2005,2)
        center=next(x for x in c['centers'] if x['fips']=='01001' and x['month']==1)
        self.assertAlmostEqual(center['log1p_prcp_mm_mean'],(math.log1p(11)+math.log1p(14))/2)
        self.assertNotAlmostEqual(center['log1p_prcp_mm_mean'],math.log1p((11+14)/2))
        self.assertFalse(c['target_values_used']);self.assertFalse(c['operational_forecast_ready'])



if __name__=='__main__':unittest.main()
