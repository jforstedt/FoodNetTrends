import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'scripts'))
from reconcile_ct_vintage2025 import reconcile, COUNTIES, YEARS


class ReconciliationTest(unittest.TestCase):
    def setUp(self):
        self.dph = []
        self.census = []
        for i in range(169):
            code = str(i+1).zfill(5)
            county = list(COUNTIES)[i % 8]
            name = 'Town ' + code
            self.dph.append(dict(STATE='09', COUSUB=code, NAME=name, v21_cousub=code,
                                 v21_county=county, CTYNAME=COUNTIES[county]+' County', COUNTY='110'))
            self.census.append(dict(SUMLEV='061', STATE='09', COUSUB=code, NAME=name, COUNTY='110',
                                    **{'POPESTIMATE'+str(y): '100' for y in YEARS}))
        self.census.append(dict(SUMLEV='040', STATE='09', **{'POPESTIMATE'+str(y): '16900' for y in YEARS}))

    def test_valid_and_unapproved(self):
        rows, mapping = reconcile(self.census, self.dph, self.dph)
        self.assertEqual(len(rows), 48)
        self.assertEqual(len(mapping), 169)
        self.assertTrue(all(r['approved_for_use'] == 'FALSE' for r in rows))
        self.assertEqual(sum(r['population'] for r in rows if r['year'] == 2025), 16900)

    def test_missing_or_duplicate_towns(self):
        for rows in (self.census[1:], self.census+self.census[:1]):
            with self.assertRaises(ValueError):
                reconcile(rows, self.dph, self.dph)

    def test_state_mismatch(self):
        self.census[-1]['POPESTIMATE2025'] = '16901'
        with self.assertRaises(ValueError):
            reconcile(self.census, self.dph, self.dph)

    def test_changed_crosswalk(self):
        other = copy.deepcopy(self.dph)
        other[0]['COUNTY'] = '120'
        with self.assertRaises(ValueError):
            reconcile(self.census, self.dph, other)

    def test_misnamed_town(self):
        self.census[0]['NAME'] = 'Wrong town'
        with self.assertRaises(ValueError):
            reconcile(self.census, self.dph, self.dph)

    def test_conflicting_dph_rows(self):
        bad = self.dph + [dict(self.dph[0], NAME='Other town')]
        with self.assertRaises(ValueError):
            reconcile(self.census, bad, bad)

    def test_invalid_population(self):
        for value in ('-1', 'nan', '1.5', '0'):
            self.census[0]['POPESTIMATE2020'] = value
            with self.assertRaises(ValueError):
                reconcile(self.census, self.dph, self.dph)


if __name__ == '__main__':
    unittest.main()
