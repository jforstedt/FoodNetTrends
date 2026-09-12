#!/usr/bin/env python3
import ast
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
root=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('comparison',str(root/'scripts/launch_comparison_refits.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
with tempfile.TemporaryDirectory() as d:
    r=Path(d)
    for file in ['bin/functions.R','scripts/refit_saved_feature.R','scripts/review_saved_fits.R']:
        (r/file).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(str(root/file),str(r/file))
    source=r/'output/fixture/spline_results';source.mkdir(parents=True)
    for key in m.KEYS:
        for suffix in ['_brm.Rds','_analysis_settings.csv','_IRCatch.csv','_IRSite.csv','_EstIRRCatch_2019_2019.csv']:
            (source/(key+suffix)).write_text('preserve fixture')
    before={p:p.read_bytes() for p in source.iterdir()}
    dest=m.prepare(r,'fixture')
    for script in ['fit.sh','review.sh']:
        subprocess.check_call(['bash','-n',str(dest/script)])
    assert all(p.read_bytes()==v for p,v in before.items())
    text=(dest/'fit.sh').read_text()
    assert all(key in text for key in m.KEYS)
    assert 'SGE_TASK_ID' in text
    assert 'diagnostic_review' in (dest/'review.sh').read_text()
    (source/(m.KEYS[0]+'_brm.Rds')).unlink()
    try:m.prepare(r,'fixture');raise AssertionError('Missing fit accepted')
    except ValueError:pass
ast.parse((root/'scripts/launch_comparison_refits.py').read_text(),feature_version=(3,6))
print('PASS: six targets, isolated outputs, source preservation, missing-fit guard, generated shell syntax, Python 3.6 syntax')
