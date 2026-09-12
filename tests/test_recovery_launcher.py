#!/usr/bin/env python3
"""Exercise recovery from a shell missing Nextflow, without submitting jobs."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

root=Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory(prefix='foodnet-recover-') as directory:
    temp=Path(directory); (temp/'scripts').mkdir(); (temp/'fakebin').mkdir(); (temp/'stubs').mkdir()
    shutil.copyfile(root/'scripts/recover_feature_run.sh',temp/'scripts/recover_feature_run.sh')
    plan=temp/'output/test/validation_plan';plan.mkdir(parents=True)
    session='89c0594f-7d1b-4779-8d94-a180597a4a6a'
    (plan/'params.json').write_text('{}')
    (plan/'nextflow.log').write_text('N E X T F L O W  ~  version 25.10.4\nSession UUID: '+session+'\n')
    (plan/'resume.sh').write_text('#!/bin/bash\nexec nextflow run main.nf -resume "$1"\n')
    (temp/'scripts/collect_run_diagnostics.py').write_text('from pathlib import Path\nPath("collected").write_text("done")\n')
    nf=temp/'stubs/nextflow';nf.write_text('#!/bin/bash\nif [[ $1 == -version ]]; then echo "Nextflow $NXF_VER"; else printf "%s\\n" "$NXF_VER" "$@" > resumed; fi\n');nf.chmod(0o755)
    singularity=temp/'stubs/singularity';singularity.write_text('#!/bin/bash\necho singularity-fixture\n');singularity.chmod(0o755)
    java=temp/'stubs/java';java.write_text('#!/bin/bash\necho java-fixture\n');java.chmod(0o755)
    setup='''module() {
  echo "$*" >> "$FIXTURE_ROOT/modules_loaded"
  case "$2" in
    nextflow/*) cp "$FIXTURE_ROOT/stubs/nextflow" "$FIXTURE_ROOT/fakebin/nextflow" ;;
    singularity/*) cp "$FIXTURE_ROOT/stubs/singularity" "$FIXTURE_ROOT/fakebin/singularity" ;;
    java/*) cp "$FIXTURE_ROOT/stubs/java" "$FIXTURE_ROOT/fakebin/java" ;;
  esac
}
export -f module
bash scripts/recover_feature_run.sh test "$1"
'''
    env=dict(os.environ,PATH=str(temp/'fakebin')+':/usr/bin:/bin',FIXTURE_ROOT=str(temp))
    p=subprocess.run(['bash','-c',setup,'fixture',session],cwd=temp,env=env,
                     stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
    assert p.returncode==0,(p.stdout,p.stderr)
    for _ in range(100):
        if (temp/'collected').exists():break
        time.sleep(.05)
    assert (temp/'collected').exists(),p.stdout+p.stderr
    assert (temp/'resumed').read_text().splitlines()==['25.10.4','run','main.nf','-resume',session]
    assert 'nextflow/24.10.4' in (temp/'modules_loaded').read_text()
    assert 'singularity/4.1.4' in (temp/'modules_loaded').read_text()
    assert 'Nextflow exit status: 0' in next(plan.glob('recovery_*.log')).read_text()
    # Do not guess a version or submit when the requested session is unrecognized.
    p=subprocess.run(['bash','scripts/recover_feature_run.sh','test','00000000-0000-0000-0000-000000000000'],cwd=temp,env=env,
                     stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
    assert p.returncode!=0 and 'no jobs started' in p.stderr
print('PASS missing-module setup, original-version pinning, detached exact-session recovery, diagnostics, and unknown-session rejection.')
