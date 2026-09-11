#!/usr/bin/env python3
"""Check fixture dashboard data and emitted JavaScript without a browser dependency."""
import json
import re
import subprocess
import sys
from pathlib import Path

html = Path(sys.argv[1]).read_text()
match = re.search(r'window.DASHBOARD_DATA = (.*?);\n', html)
assert match, 'Dashboard payload missing'
data = json.loads(match[1])
analyses = data['analyses']
assert len(analyses) >= 2
assert any(a['status'] == 'success' for a in analyses.values())
for a in analyses.values():
    if a['status'] == 'success':
        assert a['convergence_status'] == 'Not converged', a
        for rows in a['irr'].values():
            assert all(r['baseline_start'] == 2019 and r['baseline_end'] == 2019 for r in rows)
            assert all('baseline_raw_ir' in r and 'baseline_median_ir' in r for r in rows)
assert ' -entry SPLINE' not in html
for block in re.findall(r'<script\b[^>]*>(.*?)</script>', html, re.S):
    subprocess.run(['node', '-e', "let s='';process.stdin.on('data',d=>s+=d);process.stdin.on('end',()=>new(require('vm').Script)(s));"],
                   input=block, text=True, check=True)
print('Dashboard payload, baseline columns, convergence labels and JavaScript syntax passed.')
