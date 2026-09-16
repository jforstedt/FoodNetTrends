import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('context', Path(__file__).parents[1] / 'scripts/prepare_public_county_context.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)

class ContextTests(unittest.TestCase):
    def test_suppression_is_not_zero(self):
        self.assertEqual(c.numeric('(D)'), ('suppressed', ''))
        self.assertEqual(c.numeric('(Z)'), ('non_numeric_source_token', ''))
        self.assertEqual(c.numeric(''), ('missing', ''))
        self.assertEqual(c.numeric('0'), ('valid', 0.0))
        for token in ['-0.003', 'NaN', 'inf']:
            self.assertEqual(c.numeric(token)[0], 'invalid')

    def test_water_invalid_absent_and_missing_remain_distinct(self):
        rows = [{'FIPS':'27033','DO-SSPop':'-0.003','TP-TotPop':'5'},
                {'FIPS':'09001','DO-SSPop':'','TP-TotPop':'5'},
                {'FIPS':'06001','DO-SSPop':'2','TP-TotPop':'5'}]
        out = {r['fips']:r for r in c.water(['27033','09001','08014','06001'], rows, 2010, 'source')}
        self.assertEqual(out['27033']['status'], 'invalid_source_population')
        self.assertEqual(out['27033']['raw_value'], '-0.003')
        self.assertEqual(out['09001']['status'], 'missing_source_population')
        self.assertEqual(out['08014']['status'], 'absent_record')
        self.assertEqual(out['06001']['value'], .4)

    def test_actual_release_gate_not_reference_year(self):
        a = c.base('06001', 'crowded_housing_share','crowding',2010,'fraction','a')
        b = c.base('06001', 'crowded_housing_share','crowding',2012,'fraction','b')
        self.assertEqual(c.freeze([a,b],['2011-12-07']), [])
        out = c.freeze([a,b], ['2013-12-16','2013-12-17'])
        self.assertEqual([r['reference_year'] for r in out], [2010,2012])

    def test_no_fallback_to_old_valid_edition(self):
        a = c.base('06001','water','water',2005,'fraction','a'); a.update(status='valid',value=.2)
        b = c.base('06001','water','water',2010,'fraction','b'); b.update(status='invalid_source_population')
        out=c.freeze([a,b],['2011-12-31','2016-12-31'])
        self.assertEqual([r['reference_year'] for r in out],[2005,2010])
        self.assertEqual(out[1]['value'],'')

    def test_duplicate_keys_rejected(self):
        with self.assertRaises(ValueError):
            c.water(['06001'],[{'FIPS':'06001'},{'FIPS':'06001'}],2005,'x')

    def test_agriculture_definition_and_absence(self):
        row = dict(STATE_ANSI='06',COUNTY_ANSI='001', SHORT_DESC='CATTLE, INCL CALVES - INVENTORY',
                   DOMAIN_DESC='TOTAL', DOMAINCAT_DESC='NOT SPECIFIED',UNIT_DESC='HEAD',YEAR='2007',
                   AGG_LEVEL_DESC='COUNTY',VALUE='(D)',LOAD_TIME='2012-01-01')
        out=c.agriculture(['06001','06003'],[row],2007,'x',[row['SHORT_DESC']])
        self.assertEqual([r['status'] for r in out],['suppressed','absent_record'])
        self.assertEqual(out[0]['source_load_time'],'2012-01-01')
        self.assertEqual(out[0]['edition_available_by'],'2009-12-31')
        row['DOMAIN_DESC']='OTHER'
        with self.assertRaises(ValueError): c.agriculture(['06001'],[row],2007,'x',[row['SHORT_DESC']])

    def test_aggregate_water_rows_do_not_create_counties(self):
        self.assertEqual(c.water(['06001'],[{'FIPS':''},{'FIPS':''}],2005,'x')[0]['status'],'absent_record')

    def test_noncanonical_date_rejected(self):
        with self.assertRaises(ValueError): c.freeze([],['2011-1-1'])

    def test_crowding_arithmetic_and_moe_retained(self):
        e=[100,60,30,20,5,3,2,40,20,10,5,3,2]
        r={'fips':'06001','vintage':'2010','period_start':'2006','crowded_share':'.2'}
        for i,v in enumerate(e,1):
            r['B25014_%03dE'%i]=str(v); r['B25014_%03dM'%i]='1'
        out=c.crowding(['06001'],[r],'x')[0]
        self.assertEqual(out['value'],.2)
        self.assertIn('B25014_013M',out['moe_components_json'])
        r['B25014_001E']='101'
        with self.assertRaises(ValueError): c.crowding(['06001'],[r],'x')

if __name__ == '__main__': unittest.main()
