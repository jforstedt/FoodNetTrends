#!/usr/bin/env python3
"""Submit six independent saved-fit comparisons and a dependent review to SGE."""
import argparse
from datetime import datetime
from pathlib import Path
import re
import shlex
import shutil
import subprocess

KEYS=['STEC_nonO157','SALMONELLA_NONTYPHOIDAL','SALMONELLA_OTHER_SEROTYPES',
      'STEC_O157','STEC_NOT_SEROGROUPED','SALMONELLA_I_4_5_12_i_-']

def prepare(root,project):
    if not re.fullmatch('[A-Za-z0-9_-]+',project): raise ValueError('Invalid project ID')
    source=root/'output'/project
    for key in KEYS:
        for suffix in ['_brm.Rds','_analysis_settings.csv','_IRCatch.csv','_IRSite.csv','_EstIRRCatch_2019_2019.csv']:
            f=source/'spline_results'/(key+suffix)
            if not f.is_file() or not f.stat().st_size: raise ValueError('Missing saved input: '+str(f))
    dest=source/('comparison_refits_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    dest.mkdir();(dest/'spline_results').mkdir();(dest/'comparisons').mkdir()
    for src in ['bin/functions.R','scripts/refit_saved_feature.R','scripts/review_saved_fits.R']:
        shutil.copyfile(str(root/src),str(dest/Path(src).name))
    q=shlex.quote
    container=str(root/'foodnet.sif')
    common='#!/bin/bash\nset -euo pipefail\ncd '+q(str(root))+'\n'
    fit=common+'export OPENBLAS_NUM_THREADS=2\nkeys=('+ ' '.join(q(k) for k in KEYS)+')\n'
    fit+='singularity exec --bind /scicomp '+q(container)+' Rscript '+q(str(dest/'refit_saved_feature.R'))+' '+q(str(source))+' '+q(str(dest))+' "${keys[$SGE_TASK_ID-1]}"\n'
    (dest/'fit.sh').write_text(fit)
    review=common+'status=0\n'
    review+='singularity exec --bind /scicomp '+q(container)+' Rscript '+q(str(dest/'review_saved_fits.R'))+' '+q(str(dest))+' '+q(str(dest/'diagnostic_review'))+' || status=$?\n'
    review+='for key in '+ ' '.join(q(k) for k in KEYS)+'; do [[ -f '+q(str(dest))+'/"$key.status" ]] || { echo "INCOMPLETE: $key"; status=1; }; done\n'
    review+='mkdir -p '+q(str(dest/'refit_metadata'))+'\n'
    review+='cp '+q(str(dest))+'/spline_results/*_refit_settings.csv '+q(str(dest/'refit_metadata'))+'/ 2>/dev/null || true\n'
    review+='echo "Comparison review exit status: $status"\n'
    review+='tar -czf '+q(str(dest)+'.tar.gz')+' -C '+q(str(dest))+' diagnostic_review comparisons refit_metadata '+'\n'
    review+='echo '+q('Report and comparisons: '+str(dest)+'.tar.gz')+'\nexit "$status"\n'
    (dest/'review.sh').write_text(review)
    return dest

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('project');p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
    root=Path(__file__).resolve().parent.parent
    for tool in ['singularity','qsub']:
        if not shutil.which(tool): p.error('Missing '+tool+'; load the cluster modules first')
    if not (root/'foodnet.sif').is_file():p.error('foodnet.sif is missing')
    try: dest=prepare(root,a.project)
    except ValueError as e:p.error(str(e))
    print('Separate comparison directory: '+str(dest),flush=True)
    if a.prepare_only:return
    def submit(extra,script):
        argv=['qsub','-terse','-V','-cwd','-j','y','-o',str(dest)]+extra+[str(dest/script)]
        result=subprocess.check_output(argv,universal_newlines=True).strip()
        job=result.split('.')[0]
        if not job.isdigit(): raise RuntimeError('Unexpected qsub response: '+result)
        return job
    job=submit(['-N','foodnet_comparison','-t','1-6','-pe','smp','12','-l','h_rt=48:00:00,h_rss=53248M,mem_free=53248M,h_vmem=68G'],'fit.sh')
    (dest/'array_job_id.txt').write_text(job+'\n')
    print('Six refits submitted as array job '+job+'; SGE controls concurrency.',flush=True)
    review=submit(['-N','foodnet_comparison_review','-hold_jid',job,'-pe','smp','1','-l','h_rt=02:00:00,h_rss=16384M,mem_free=16384M,h_vmem=32G'],'review.sh')
    (dest/'review_job_id.txt').write_text(review+'\n')
    print('Automatic review job: '+review+'\nFinal archive: '+str(dest)+'.tar.gz',flush=True)

if __name__=='__main__': main()
