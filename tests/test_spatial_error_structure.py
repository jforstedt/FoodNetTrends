import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import review_spatial_error_structure as r


class SpatialErrorStructureTests(unittest.TestCase):
    def rows(self):
        rows=[]
        for cutoff,gain in ((2011,1),(2013,2),(2016,-3)):
            for state in ('CA','CO'):
                for year in range(cutoff+1,cutoff+4):
                    for stream in range(5):
                        rows.append(dict(pathogen='YERSINIA',cutoff=cutoff,temporal='ar1',seasonal=False,state=state,year=year,stream=stream,score_gain=gain,observed=10,iid_expected=12,bym2_expected=11,iid_covered=1,bym2_covered=1,iid_width=5,bym2_width=4,iid_abs_error=2,bym2_abs_error=1,iid_tail_share=.01,bym2_tail_share=.01))
        return rows

    def test_equal_block_concentration_and_omission(self):
        grouped,omitted,concentration=r.tables(self.rows())
        overall=r.summarize(self.rows())
        self.assertEqual(overall['score_gain'],0)
        origin=next(x for x in concentration if x['dimension']=='cutoff')
        self.assertEqual(origin['largest_absolute_share'],.5)
        self.assertEqual(origin['largest_absolute_block'],2016)
        removed=next(x for x in omitted if x['dimension']=='cutoff' and x['omitted']==2016)
        self.assertEqual(removed['remaining_score_gain'],1.5)
        self.assertAlmostEqual(overall['iid_relative_bias'],.2)
        self.assertAlmostEqual(overall['bym2_relative_bias'],.1)

    def test_zero_observed_bias_undefined(self):
        rows=self.rows()
        for row in rows:row['observed']=0
        self.assertEqual(r.summarize(rows)['iid_relative_bias'],'')

    def test_streams_not_counted_as_new_observations(self):
        rows=self.rows()
        for row in rows:
            if row['stream']!=0:row['score_gain']=100
        result=r.summarize(rows)
        self.assertEqual(result['score_gain'],0)
        self.assertEqual(result['n_state_year_evaluations'],18)
        self.assertEqual(result['stream_gain_min'],100)

    def test_partial_and_duplicate_grids_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            (folder/'review_summary.json').write_text(json.dumps(dict(complete=324,complete_three_origin_configurations=54,scientific_acceptance=False)))
            rows=self.rows()
            for data in (rows,rows+[rows[0]]):
                with (folder/'paired_site_metrics_LOCAL.csv').open('w',newline='') as handle:
                    writer=csv.DictWriter(handle,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)
                with self.assertRaises(ValueError):r.read_verified(folder)


if __name__=='__main__':unittest.main()
