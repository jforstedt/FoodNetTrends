#!/usr/bin/env python3
"""Execute one fingerprinted forecast-validation task, enforcing prerequisite success."""
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from county_forecast_artifacts import validate_task_outputs


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def _run_locked(dest,task_id):
    dest=Path(dest);manifest_path=dest/'manifest.json';plan=json.loads(manifest_path.read_text())
    matches=[t for t in plan['tasks'] if t['id']==task_id]
    if len(matches)!=1:raise ValueError('Task is not uniquely declared')
    task=matches[0];work=dest/task_id;work.mkdir(exist_ok=True);status_path=work/'task_status.json'
    identity=hashlib.sha256(json.dumps(dict(task=task,fingerprints=plan['fingerprints']),sort_keys=True).encode()).hexdigest()
    # Completed outputs may be reused only when every recorded artifact still matches.
    if status_path.exists():
        old=json.loads(status_path.read_text())
        if old.get('status')=='COMPLETE' and old.get('task_sha256')==identity and old.get('outputs'):
            if old.get('exit_status')==0 and all((work/p).is_file() and sha(work/p)==h for p,h in old['outputs'].items()) and all(sha(p)==h for p,h in dict(plan['fingerprints'],**task.get('input_fingerprints',{})).items()):
                if task['kind']=='forecast':
                    gate=json.loads((dest/'gate.json').read_text())
                    if gate.get('manifest_sha256')!=sha(manifest_path) or gate.get('status')!='PASS':
                        raise ValueError('Completed task cannot bypass a revoked or changed prerequisite gate')
                validate_task_outputs(work,task)
                return 0
        raise ValueError('Existing task attempt is incomplete/changed; retain it and prepare a fresh recovery attempt')
    result=dict(status='FAILED',exit_status=1,task_sha256=identity)
    try:
        for path,h in plan['fingerprints'].items():
            if sha(path)!=h:raise ValueError('Shared source/container fingerprint changed: '+path)
        for path,h in task.get('input_fingerprints',{}).items():
            if sha(path)!=h:raise ValueError('Task input fingerprint changed: '+path)
        if task['kind']=='forecast':
            if not plan.get('inputs_verified'):raise ValueError('Plan inputs are unverified; prepare-only plans cannot fit real data')
            gate=json.loads((dest/'gate.json').read_text())
            if gate.get('manifest_sha256')!=sha(manifest_path) or gate.get('status')!='PASS':
                result.update(status='BLOCKED_GATE',exit_status=2,reason='Numerical/calibration prerequisites did not pass')
                return 2
        with (work/'task.log').open('w') as log:
            code=subprocess.run(task['command'],stdout=log,stderr=subprocess.STDOUT,cwd=str(dest)).returncode
        result.update(exit_status=code,status='COMPLETE' if code==0 else 'FAILED')
        for path,h in task.get('input_fingerprints',{}).items():
            if sha(path)!=h:raise ValueError('Task inputs changed during execution: '+path)
        if code==0:
            for path,h in plan['fingerprints'].items():
                if sha(path)!=h:raise ValueError('Shared source/container changed during execution: '+path)
            result['artifact_validation']=validate_task_outputs(work,task)
            result['outputs']={str(p.relative_to(work)):sha(p) for p in work.rglob('*') if p.is_file() and p.suffix.lower() in ('.csv','.json','.txt','.pdf') and p!=status_path}
            if not result['outputs']:raise ValueError('Task returned success without validation artifacts')
        return code
    except (OSError,ValueError,KeyError,TypeError,IndexError) as e:
        result.update(status='FAILED',exit_status=1,reason=str(e));return 1
    finally:
        temp=work/'task_status.json.tmp';temp.write_text(json.dumps(result,indent=2)+'\n');temp.replace(status_path)
def run(dest,task_id):
    dest=Path(dest)
    plan=json.loads((dest/'manifest.json').read_text())
    if len([t for t in plan['tasks'] if t['id']==task_id])!=1:
        raise ValueError('Task is not uniquely declared')
    work=dest/task_id;work.mkdir(exist_ok=True)
    # Keep this descriptor open through validation, execution and atomic status publication.
    # A duplicate invocation must not write into a currently running task directory.
    with (work/'.task.lock').open('a') as lock:
        try:
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Task already has an active runner; no outputs changed: '+task_id)
        try:
            return _run_locked(dest,task_id)
        finally:
            fcntl.flock(lock.fileno(),fcntl.LOCK_UN)


if __name__=='__main__':sys.exit(run(sys.argv[1],sys.argv[2]))
