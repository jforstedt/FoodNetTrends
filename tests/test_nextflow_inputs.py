#!/usr/bin/env python3
"""Check CLI input validation using the installed Nextflow version."""
import os
import subprocess
import tempfile
from pathlib import Path

root=Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory(prefix='foodnet-cli-') as temp:
    base=['nextflow','run',str(root/'main.nf'),'-profile','test',
          '-c',str(root/'tests/integration.config'),'--custom_config_base',temp,
          '--outdir',str(Path(temp)/'output'),'-ansi-log','false']
    for args,message in [(['--pathogen',''],'Invalid --pathogen:'),
                         (['--pathogen',', , '],'Invalid --pathogen:'),
                         (['--pathogen_grouping',''],'Invalid --pathogen_grouping:'),
                         (['--colorado_coverage','unknown'],'colorado_coverage must be'),
                         (['--parasite_end_year','oops'],'parasite_end_year must be')]:
        p=subprocess.run(base+args,cwd=temp,env={**os.environ,'NXF_OFFLINE':'true'},
                         text=True,capture_output=True,timeout=90)
        assert p.returncode!=0 and message in p.stdout+p.stderr,p.stdout+p.stderr
        assert 'Submitted process' not in p.stdout+p.stderr
print('Nextflow rejects blank/comma-only pathogen lists and empty grouping options before submitting tasks.')
