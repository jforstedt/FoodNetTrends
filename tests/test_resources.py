#!/usr/bin/env python3
"""Resolve actual repository selectors under Nextflow, including CPU-only overrides."""
import os
from pathlib import Path
import subprocess
import tempfile

root=Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory(prefix='foodnet-resources-') as directory:
    temp=Path(directory)
    (temp/'main.nf').write_text('''process TRENDY {
    cpus 1
    memory '8 GB'
    time '4h'
    output:
    stdout
    script:
    "echo '${task.cpus}|${task.memory.toGiga()}|${task.time.toHours()}'"
}
workflow FOODNETTRENDS { TRENDY().view() }
workflow { FOODNETTRENDS() }
''')
    config=temp/'probe.config'
    base="""
process.executor = 'local'
process.clusterOptions = ''
process.penv = null
executor.memory = '128 GB'
executor.cpus = 16
params.chains = 6
params.stan_backend = 'rstan'
"""
    for label,extra,expected in [
        ('default','', '12|52|48'),
        ('CPU-only override',"process { withName: 'FOODNETTRENDS:TRENDY' { cpus = 6 } }",'6|52|48'),
        ('cmdstan',"params.stan_backend = 'cmdstanr'",'8|16|48'),
        ('caps',"params.max_cpus=2\nparams.max_memory='2 GB'\nparams.max_time='1h'",'2|2|1'),
    ]:
        config.write_text(base+extra)
        p=subprocess.run(['nextflow','run',str(temp/'main.nf'),'-c',str(root/'nextflow.config'),
                          '-c',str(config),'--custom_config_base',str(temp),
                          '--outdir',str(temp/'output'),'-ansi-log','false'],
                         cwd=temp,env=dict(os.environ,NXF_OFFLINE='true'),
                         stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,timeout=120)
        assert p.returncode==0 and expected in p.stdout,(label,p.stdout,p.stderr)
        print('PASS {}: {}'.format(label,expected),flush=True)
