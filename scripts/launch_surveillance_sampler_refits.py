#!/usr/bin/env python3
"""Submit only divergence-flagged saved surveillance models and automatic review."""
import argparse
import copy
from datetime import datetime
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
from collect_surveillance_refits import sha256

DEFAULT_AUDIT='surveillance_postrun_audit_20260913_034836_194880'

def prepare(root,audit,dest):
    audit=Path(audit).resolve()
    review=json.loads((audit/'review_summary.json').read_text())
    summary=json.loads((audit/'postrun_summary.json').read_text())
    source=Path(review['source_run']); manifest=json.loads((source/'manifest.json').read_text())
    if summary['listeria_status']!='PASS' or not summary['container_unchanged']:raise ValueError('Input/container audit did not pass')
    if json.loads((audit/'source_manifest.json').read_text())!=manifest:raise ValueError('Source manifest differs from audit snapshot')
    reviewed={r['task']:r for r in review['results']}
    container=root/'foodnet.sif'
    if sha256(container)!=summary['container_sha256']:raise ValueError('Container differs from audited image')
    selected=[];retained=[]
    for job in manifest['jobs']:
        proof=json.loads((audit/job['task']/'saved_fit_validation.json').read_text())
        old=source/job['task'];fit=old/'spline_results'/(job['prefix']+'_brm.Rds')
        if sha256(fit)!=proof['fit_sha256']:raise ValueError('Saved fit differs from audited checkpoint')
        if proof['status']=='PASS':
            if reviewed[job['task']]['status']!='CHECKS_PASS':raise ValueError('Retained output failed artifact review: '+job['prefix'])
            retained.append(job['prefix']);continue
        if proof['eligibility_status']!='PASS' or proof['issues']!=['Divergent transitions present']:
            raise ValueError('Non-divergence issue requires review: '+job['prefix'])
        old=source/job['task'];fit=old/'spline_results'/(job['prefix']+'_brm.Rds')
        if sha256(fit)!=proof['fit_sha256']:raise ValueError('Saved fit differs from audited checkpoint')
        selected.append((job,old,proof))
    if not selected:raise ValueError('No divergence-only fits need refitting')
    for n,h in manifest['source_sha256'].items():
        if sha256(source/'scripts'/n)!=h:raise ValueError('Original source snapshot changed: '+n)
    dest.mkdir(parents=True,exist_ok=False);scripts=dest/'scripts';scripts.mkdir();q=shlex.quote
    for n in manifest['source_sha256']:shutil.copyfile(str(source/'scripts'/n),str(scripts/n))
    for n in ('refit_surveillance_sampler.R','audit_saved_state_fit.R','collect_surveillance_refits.py'):
        shutil.copyfile(str(root/'scripts'/n),str(scripts/n))
    jobs=[]
    for i,(job,old,proof) in enumerate(selected,1):
        j=copy.deepcopy(job);work=dest/('task_%02d'%i);work.mkdir();(work/'spline_results').mkdir();(work/'comparisons').mkdir()
        j.update(task=work.name,original_task=str(old),adapt_delta='0.9999')
        for n in ('classification_rules.csv','source_settings.csv'):shutil.copyfile(str(old/n),str(work/n))
        shutil.copyfile(str(scripts/'functions.R'),str(work/'functions.R'))
        (work/'source_fit_sha256.txt').write_text(proof['fit_sha256']+'\n')
        (work/'source_validation.json').write_text(json.dumps(proof,indent=2)+'\n')
        common=['singularity','exec','--cleanenv','--env','OPENBLAS_NUM_THREADS=2,OMP_NUM_THREADS=2,MKL_NUM_THREADS=2','--bind','/scicomp','--bind',str(source)+':'+str(source)+':ro',str(container),'Rscript','--vanilla']
        fitcmd=common+[str(scripts/'refit_surveillance_sampler.R'),str(old),str(work),j['prefix']]
        auditcmd=common+[str(scripts/'audit_saved_state_fit.R'),str(work),str(work/'saved_fit_validation.json')]
        j['sampler_refit_command']=fitcmd
        checked=[container,work/'functions.R',work/'classification_rules.csv']+list(scripts.iterdir())
        (work/'checksums.sha256').write_text(''.join(sha256(f)+'  '+str(f)+'\n' for f in checked))
        shell='#!/bin/bash\nset -uo pipefail\nstatus=0\nif sha256sum --check '+q(str(work/'checksums.sha256'))+' > '+q(str(work/'integrity.log'))+' 2>&1; then\n  '+' '.join(map(q,fitcmd))+' > '+q(str(work/'fit.log'))+' 2>&1 || status=$?\nelse\n  status=1\nfi\n'
        shell+='printf "%s\\n" "$status" > '+q(str(work/'exit_status.txt'))+'\nif [ "$status" -eq 0 ]; then\n  audit_status=0\n  '+' '.join(map(q,auditcmd))+' > '+q(str(work/'audit.log'))+' 2>&1 || audit_status=$?\n  printf "%s\\n" "$audit_status" > '+q(str(work/'audit_exit_status.txt'))+'\nfi\nexit "$status"\n'
        (work/'run.sh').write_text(shell);jobs.append(j)
    hashes={f.name:sha256(f) for f in scripts.iterdir() if f.is_file()}
    (dest/'manifest.json').write_text(json.dumps(dict(jobs=jobs,source_sha256=hashes,source_run=str(source),source_audit=str(audit),retained_passing_models=retained,container_sha256=summary['container_sha256'],pending_review=['Review remaining divergences and estimate differences before dashboard replacement'],model_change='Only adapt_delta=0.9999; saved data, numeric priors and Stan code must match exactly.'),indent=2)+'\n')
    (dest/'array.sh').write_text('#!/bin/bash\nset -euo pipefail\nprintf -v task "task_%02d" "$SGE_TASK_ID"\nexec bash '+q(str(dest))+'/"$task"/run.sh\n')
    (dest/'collect.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec python3 '+q(str(scripts/'collect_surveillance_refits.py'))+' '+q(str(dest))+'\n')
    return len(jobs)

def main():
    root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audit',type=Path,default=root/'output'/DEFAULT_AUDIT);p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
    if not a.prepare_only:
        for tool in ('qsub','singularity'):
            if not shutil.which(tool):p.error('Load module for '+tool)
    dest=root/'output'/('surveillance_sampler_refits_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    print('Checking audited checkpoints and container hashes before submission; large files may take a few minutes.',flush=True)
    try:n=prepare(root,a.audit,dest)
    except (ValueError,KeyError,OSError) as e:p.error(str(e))
    print('Output: '+str(dest)+'\nModels to refit: '+str(n),flush=True)
    if a.prepare_only:return
    def submit(extra,script):
        answer=subprocess.check_output(['qsub','-terse','-V','-cwd','-S','/bin/bash','-j','y','-o',str(dest)]+extra+[str(dest/script)],universal_newlines=True).strip()
        jid=answer.split('.')[0]
        if not jid.isdigit():raise RuntimeError('Unexpected qsub response: '+answer)
        return jid
    jid=submit(['-N','foodnet_sampler','-t','1-'+str(n),'-pe','smp','12','-l','h_rt=48:00:00,h_rss=53248M,mem_free=53248M,h_vmem=68G'],'array.sh')
    (dest/'array_job_id.txt').write_text(jid+'\n');print('Fit array: '+jid,flush=True)
    final=submit(['-N','foodnet_sampler_review','-hold_jid',jid,'-pe','smp','1','-l','h_rt=02:00:00,h_rss=16384M,mem_free=16384M,h_vmem=32G'],'collect.sh')
    (dest/'collection_job_id.txt').write_text(final+'\n')
    print('Automatic collection job: '+final+'\nArchive: '+str(dest)+'.tar.gz\nAfter both job IDs appear, these scheduler jobs continue independently of your terminal.')
if __name__=='__main__':main()
