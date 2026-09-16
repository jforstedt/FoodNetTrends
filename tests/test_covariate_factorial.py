import copy
import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import prepare_covariate_factorial as m


def fixture():
    weather=[dict(fips=f,year=str(y),month=str(month),tavg_c=str(month+(y-2004)*2+i),prcp_mm=str(20+month+(y-2004)*3+i))
             for i,f in enumerate(('01001','01003')) for y in range(2003,2009) for month in range(1,13)]
    age=[dict(fips=f,year=str(y),under5_share=str(.04+.005*i+.001*(y-2004)),age65plus_share=str(.12+.02*i+.002*(y-2004)))
         for i,f in enumerate(('01001','01003')) for y in range(2004,2009)]
    return weather,age


class FactorialFeatures(unittest.TestCase):
    def test_matched_support_training_standardization_and_no_mutation(self):
        w,a=fixture();before=copy.deepcopy((w,a))
        current,c=m.transform(w,a,2005,'current',2);lag,l=m.transform(w,a,2005,'lag01',2)
        self.assertEqual((w,a),before)
        self.assertEqual([(r['fips'],r['year'],r['month']) for r in current],[(r['fips'],r['year'],r['month']) for r in lag])
        for column in ('age_under5_z','age65plus_z','weather_tavg_z','weather_logprcp_z'):
            values=[r[column] for r in lag if r['year']<=2005]
            self.assertAlmostEqual(sum(values)/len(values),0)
            self.assertAlmostEqual(sum(x*x for x in values)/len(values),1)
        self.assertEqual(c['age_centers'],l['age_centers']);self.assertEqual(l['lag_weights'],[.5,.5])

    def test_no_future_information_in_transform_parameters(self):
        w,a=fixture();_,before=m.transform(w,a,2005,'lag01',2)
        for r in w:
            if int(r['year'])>2005:r.update(tavg_c='99',prcp_mm='999')
        for r in a:
            if int(r['year'])>2005:r.update(under5_share='.2',age65plus_share='.3')
        _,after=m.transform(w,a,2005,'lag01',2)
        for name in ('centers','scales','age_centers','age_scales'):self.assertEqual(before[name],after[name])

    def test_actual_previous_december_and_transform_order(self):
        w,a=fixture();_,c=m.transform(w,a,2005,'lag01',2)
        center=next(x for x in c['centers'] if x['fips']=='01001' and x['month']==1)
        # Jan04=21,Dec03=29;Jan05=24,Dec04=32; average LOG amounts then calendar mean.
        self.assertAlmostEqual(center['log1p_prcp_mm_mean'],sum(math.log1p(x) for x in (21,29,24,32))/4)
        w=[r for r in w if not(r['year']=='2003' and r['month']=='12')]
        with self.assertRaisesRegex(ValueError,'previous-month'):m.transform(w,a,2005,'lag01',2)
        m.transform(w,a,2005,'current',2)

    def test_missing_duplicate_invalid_age_rejected(self):
        w,a=fixture()
        with self.assertRaisesRegex(ValueError,'Missing age'):m.transform(w,a[1:],2005,'current',2)
        with self.assertRaisesRegex(ValueError,'Duplicate age'):m.transform(w,a+[a[0]],2005,'current',2)
        a[0]['under5_share']='.95'
        with self.assertRaisesRegex(ValueError,'disjoint'):m.transform(w,a,2005,'current',2)


if __name__=='__main__':unittest.main()
