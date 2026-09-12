#!/usr/bin/env python3
"""Exercise synthetic launch plans without a cluster, INLA, or surveillance data."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile


root = Path(__file__).resolve().parent.parent


def run(argv, env):
    return subprocess.run(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True)


with tempfile.TemporaryDirectory(prefix='inla-launch-') as temp:
    base = Path(temp)
    fixture = base / "repo space ' $(touch INJECTION)"
    (fixture / 'scripts').mkdir(parents=True)
    shutil.copyfile(str(root / 'scripts/launch_inla_smoke.py'), str(fixture / 'scripts/launch_inla_smoke.py'))
    (fixture / 'scripts/inla_smoke.R').write_text('# synthetic fixture\n')
    launcher = [sys.executable, str(fixture / 'scripts/launch_inla_smoke.py')]
    # Preparation works even with no commands on PATH and no image.
    result = run(launcher + ['--prepare-only'], dict(os.environ, PATH=''))
    assert result.returncode == 0, result.stderr
    destination = next((fixture / 'output').iterdir())
    assert (destination / 'inla_smoke.R').read_text() == '# synthetic fixture\n'
    manifest = json.loads((destination / 'plan.json').read_text())
    assert manifest['command'][1:3] == ['exec', '--cleanenv']
    assert manifest['command'][-2:] == [str(destination / 'reports'), '2']
    assert ':ro' in manifest['command'][4] and ':rw' in manifest['command'][6]
    assert not (fixture / 'foodnet-inla.sif').exists()
    fakebin = base / 'bin'
    fakebin.mkdir()
    singularity = fakebin / 'singularity'
    singularity.write_text('#!' + sys.executable + '\nimport json, os, sys\n'
                           'open(os.environ["ARGV_FILE"], "w").write(json.dumps(sys.argv[1:]))\n'
                           'if os.listdir(sys.argv[-2]):\n'
                           '    print("ERROR: report directory must be empty")\n'
                           '    sys.exit(99)\n'
                           'print("synthetic diagnostic output")\n'
                           'sys.exit(int(os.environ.get("SMOKE_STATUS", "0")))\n')
    singularity.chmod(0o755)
    env = dict(os.environ, PATH=str(fakebin) + os.pathsep + os.environ['PATH'],
               ARGV_FILE=str(base / 'argv.json'))
    for status in (0, 7):
        for report in (destination / 'reports').iterdir():
            report.unlink()
        env['SMOKE_STATUS'] = str(status)
        result = run(['bash', str(destination / 'run.sh')], env)
        assert result.returncode == status, (result.stdout, result.stderr)
        assert json.loads((base / 'argv.json').read_text()) == manifest['command'][1:]
        assert (destination / 'reports/exit_status.txt').read_text().strip() == str(status)
        with tarfile.open(str(destination) + '.tar.gz') as archive:
            assert archive.extractfile('reports/exit_status.txt').read().decode().strip() == str(status)
            assert b'synthetic diagnostic output' in archive.extractfile('reports/smoke.log').read()
            assert archive.extractfile('inla_smoke.R').read() == b'# synthetic fixture\n'
    assert not (destination / 'INJECTION').exists()
    # Verify a real launcher submission's exact qsub argv using a stub.
    qsub = fakebin / 'qsub'
    qsub.write_text('#!' + sys.executable + '\nimport json, os, sys\n'
                    'open(os.environ["QSUB_ARGV"], "w").write(json.dumps(sys.argv[1:]))\n'
                    'print("12345")\n')
    qsub.chmod(0o755)
    container = base / "image space ' $(touch BAD).sif"
    container.write_text('fixture')
    env['QSUB_ARGV'] = str(base / 'qsub.json')
    result = run(launcher + ['--container', str(container)], env)
    assert result.returncode == 0 and 'job: 12345' in result.stdout, result.stderr
    submitted = json.loads((base / 'qsub.json').read_text())
    assert submitted[submitted.index('-pe') + 1:submitted.index('-pe') + 3] == ['smp', '2']
    assert 'h_rt=00:30:00' in submitted[submitted.index('-l') + 1]
    submitted_dir = Path(submitted[-1]).parent
    assert json.loads((submitted_dir / 'plan.json').read_text())['container'] == str(container)
    # Archive failure must fail an otherwise successful check without masking R failures.
    fake_tar = fakebin / 'tar'
    fake_tar.write_text('#!/bin/bash\nexit 13\n')
    fake_tar.chmod(0o755)
    for model_status, expected_status in ((0, 13), (7, 7)):
        for report in (submitted_dir / 'reports').iterdir():
            report.unlink()
        env['SMOKE_STATUS'] = str(model_status)
        result = run(['bash', str(submitted_dir / 'run.sh')], env)
        assert result.returncode == expected_status
        assert 'Archive failed: 13' in result.stderr

print('PASS offline planning, quoted paths, qsub resources, logs/archives, and failure exit propagation.')
