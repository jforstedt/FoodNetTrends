import itertools
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import review_monthly_classification_results as r
import test_monthly_classification_models as fixtures


class ClassificationReviewTests(unittest.TestCase):
    def scores(self):
        rows=[]
        for b,t,s in itertools.product((0,1),repeat=3):
            score=-100+2*t+3*s+5*b+7*t*s+11*b*s+13*b*t+17*b*t*s
            rows.append(dict(pathogen='SALMONELLA',cutoff=2015,level='county',spatial='bym2' if b else 'iid',temporal='ar1' if t else 'rw1',seasonal=bool(s),state='CA',year=2016,stream=0,eligible_cells=12,mean_log_score=score))
        return rows

    def test_factorial_interactions(self):
        results=r.interactions(self.scores())
        self.assertEqual(len(results),7)
        triple=next(x for x in results if x['interaction']=='spatial_x_temporal_x_seasonality')
        self.assertEqual(triple['score_interaction'],17)
        ts={x['fixed_spatial']:x['score_interaction'] for x in results if x['interaction']=='temporal_x_seasonality'}
        self.assertEqual(ts,{'iid':7,'bym2':24})

    def test_component_contrasts_remain_within_resolution(self):
        results=r.contrasts(self.scores())
        self.assertEqual(len(results),12)
        simple=next(x for x in results if x['contrast']=='bym2_minus_iid' and x['temporal']=='rw1' and not x['seasonal'])
        self.assertEqual(simple['score_gain'],5)
        self.assertEqual(simple['level'],'county')

    def test_incomplete_and_changed_support_rejected(self):
        with self.assertRaises(ValueError):r.interactions(self.scores()[:-1])
        rows=self.scores();rows[0]['eligible_cells']=11
        with self.assertRaises(ValueError):r.interactions(rows)
        with self.assertRaises(ValueError):r.contrasts(rows)

    def test_undefined_scores_not_zero(self):
        rows=self.scores()
        for row in rows:row.update(mean_log_score=None,eligible_cells=0)
        self.assertTrue(all(x['score_interaction'] is None for x in r.interactions(rows)))
        self.assertTrue(all(x['score_gain'] is None for x in r.contrasts(rows)))
        rows[0]['mean_log_score']=-1
        with self.assertRaises(ValueError):r.contrasts(rows)

    def test_portable_validation_does_not_weaken_worker_default(self):
        fixture=fixtures.ClassificationModelLauncherTests()
        with tempfile.TemporaryDirectory() as td:
            work,task=fixture.fixture(Path(td));(work/'result/fit_INTERNAL.rds').unlink()
            with self.assertRaisesRegex(ValueError,'Missing saved fit'):r.model.validate(work,task)
            self.assertTrue(r.model.validate(work,task,require_internal=False))
            (work/'result/fit_diagnostics.csv').write_text('fit_ok,mode_status\nTRUE,2\n')
            with self.assertRaisesRegex(ValueError,'Numerical'):r.model.validate(work,task,require_internal=False)


if __name__=='__main__':unittest.main()
