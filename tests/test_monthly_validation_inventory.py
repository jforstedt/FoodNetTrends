import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('inventory', str(ROOT / 'scripts/inventory_monthly_validation.py'))
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


class ValidationInventoryTest(unittest.TestCase):
    def test_all_pathogens_and_overlap_not_independent(self):
        summaries, years = inventory.inventory()
        self.assertEqual(len(summaries), 9)
        self.assertEqual(len(years), 9 * 22)
        self.assertTrue(all(not r['independent_holdout_certified'] for r in years))
        salmonella = next(r for r in years if r['pathogen'] == 'SALMONELLA' and r['year'] == 2014)
        self.assertEqual(salmonella['evaluation_origins'], '2011;2013')
        self.assertEqual(salmonella['training_origins'], '2016')
        self.assertEqual(salmonella['period_status'], 'DEVELOPMENT_EXPOSED')

    def test_pathogen_boundaries_are_not_new_holdouts(self):
        _, years = inventory.inventory()
        lookup = {(r['pathogen'], r['year']): r for r in years}
        self.assertEqual(lookup['CRYPTOSPORIDIUM', 2018]['period_status'], 'OUTSIDE_CONFIRMED_SURVEILLANCE')
        self.assertEqual(lookup['CAMPYLOBACTER', 2024]['period_status'], 'DIAGNOSTIC_REPORTING_BREAK')
        self.assertEqual(lookup['LISTERIA', 2025]['period_status'], 'REPORTING_COMPLETENESS_UNESTABLISHED')
        self.assertEqual(lookup['SALMONELLA', 2022]['period_status'], 'UNASSESSED_EXTENSION_NOT_CONFIRMED_HOLDOUT')
        self.assertEqual(lookup['STEC', 2025]['period_status'], 'UNASSESSED_EXTENSION_NOT_CONFIRMED_HOLDOUT')

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / 'inventory'
            inventory.write_inventory(dest)
            self.assertTrue((dest / 'year_inventory.csv').is_file())
            with self.assertRaises(FileExistsError):
                inventory.write_inventory(dest)


if __name__ == '__main__':
    unittest.main()
