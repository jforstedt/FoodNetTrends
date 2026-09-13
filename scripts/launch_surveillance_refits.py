#!/usr/bin/env python3
"""Refit only saved state analyses affected by documented surveillance windows."""
import argparse
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess

DEFAULT_SOURCES = ('output/20260911_140750/spline_results', 'output/feature_validation_20260911_182917_961728/final_dashboard_20260912_173916_851341/spline_results')

def rows(path):
    with path.open(newline='') as handle:
        return list(csv.DictReader(handle))

def scan(sources):
    jobs=[]
    for source in sources:
        files=sorted(source.glob('*_analysis_settings.csv'))
        if not files: raise ValueError('No saved analysis settings: '+str(source))
        for f in files:
            saved=rows(f)
            if len(saved)!=1: raise ValueError('Expected one settings row: '+str(f))
            s=saved[0];pathogen=s['pathogen'];group=s['subgroup']
            if pathogen=='CRYPTOSPORIDIUM': continue
            start=int(s['analysis_start_year']);end=int(s['analysis_end_year']);reasons=[]
            if pathogen=='CAMPYLOBACTER' and end>2023:
                end=2023;reasons.append('CIDT-only surveillance discontinued after 2023')
            if pathogen=='STEC' and group.lower()=='nono157' and start<2000:
                start=2000;reasons.append('Non-O157 surveillance began in 2000')
            if pathogen not in ('SALMONELLA','STEC') and end>=2025:
                end=2024;reasons.append('2025 reporting completeness unverified after optional reporting began')
            if not reasons: continue
            for key in ('travel','cidt','states','colorado_coverage','parasite_end_year','serotype_source','selected_serotypes','baseline_start','baseline_end'):
                if key not in s: raise ValueError('Cannot preserve missing setting '+key+': '+str(f))
            states=s['states'].strip()
            if states and any(not re.fullmatch('[A-Z]{2}',v) for v in states.split(',')):
                raise ValueError('Unrecognized saved state selection: '+str(f))
            if not start<=int(s['baseline_start'])<=int(s['baseline_end'])<=end:
                raise ValueError('Baseline outside corrected surveillance years; explicit baseline decision required: '+str(f))
            if s.get('catchment_config','').strip(): raise ValueError('Custom catchment requires explicit preservation review: '+str(f))
            prefix=f.name[:-len('_analysis_settings.csv')]
            rules=source/(prefix+'_classification_rules.csv')
            if not rules.is_file(): raise ValueError('Missing saved classification rules: '+str(rules))
            params={}
            for candidate in (source.parent/'params.json',source.parent/'validation_plan/params.json'):
                if candidate.is_file(): params=json.loads(candidate.read_text());break
            known_default=any(str(source.resolve()).endswith('/'+v) for v in DEFAULT_SOURCES)
            if not known_default and not params and not all(k in s for k in ('travel_stratify','catchment_config')):
                raise ValueError('Alternate source lacks travel-stratification/custom-catchment provenance: '+str(f))
            if params and 'travel_stratify' not in params and 'travel_stratify' not in s:
                raise ValueError('Source parameters do not establish travel-stratification setting: '+str(f))
            if params.get('catchment_config'): raise ValueError('Custom catchment requires explicit preservation review: '+str(f))
            strat=s.get('travel_stratify',params.get('travel_stratify',False))
            if str(strat).lower() not in ('false','0',''): raise ValueError('Travel-stratified source requires separate recovery plan: '+str(f))
            jobs.append(dict(source=str(source),settings=s,prefix=prefix,rules=str(rules),first_year=start,last_year=end,reasons=reasons,
                             adapt_delta='0.999' if 'feature_validation_' in str(source) else '0.99'))
    return jobs

def prepare(root,dest,data,sources,clean=None):
    jobs=scan(sources)
    if not jobs: raise ValueError('No affected saved analyses found; no jobs submitted')
    dest.mkdir(parents=True,exist_ok=False);scripts=dest/'scripts';scripts.mkdir();hashes={}
    for name in ('trendy.R','functions.R','classification.R','input_validation.R'):
        src=root/'bin'/name;shutil.copyfile(str(src),str(scripts/name));hashes[name]=hashlib.sha256(src.read_bytes()).hexdigest()
    auditor=root/'scripts/audit_saved_state_fit.R'
    shutil.copyfile(str(auditor),str(scripts/auditor.name))
    hashes[auditor.name]=hashlib.sha256(auditor.read_bytes()).hexdigest()
    shutil.copyfile(str(root/'scripts/collect_surveillance_refits.py'),str(dest/'collect.py'))
    clean=clean or root/'output/20260911_140750/preprocessed/clean_mmwr.csv'
    q=shlex.quote
    for i,job in enumerate(jobs,1):
        work=dest/('task_%02d'%i);work.mkdir();(work/'spline_results').mkdir();s=job['settings']
        shutil.copyfile(job['rules'],str(work/'classification_rules.csv'))
        job['classification_sha256']=hashlib.sha256((work/'classification_rules.csv').read_bytes()).hexdigest()
        shutil.copyfile(str(Path(job['source'])/(job['prefix']+'_analysis_settings.csv')),str(work/'source_settings.csv'))
        command=['singularity','exec','--cleanenv','--env','OPENBLAS_NUM_THREADS=2,OMP_NUM_THREADS=2,MKL_NUM_THREADS=2','--bind','/scicomp',str(root/'foodnet.sif'),'Rscript','--vanilla',str(scripts/'trendy.R')]
        options={'mmwrFile':str(data/'mmwr9625.sas7bdat'),'censusFileB':str(data/'cen9625.sas7bdat'),'censusFileP':str(data/'cen9625_para.sas7bdat'),
          'preprocessed':'TRUE','cleanFile':str(clean),'pathogen':s['pathogen'],'subgroup':s['subgroup'],'outDir':str(work/'spline_results'),'projID':dest.name,
          'cores':'12','chains':'6','iterations':'10001','adapt_delta':job['adapt_delta'],'max_treedepth':'15','seed':'123','backend':'rstan',
          'analysis_end_year':str(job['last_year']),'classification_rules':str(work/'classification_rules.csv'),'travel_stratify':'false','debug':'FALSE'}
        for key in ('travel','cidt','baseline_start','baseline_end','colorado_coverage','parasite_end_year','serotype_source','selected_serotypes'):
            options[key]=s[key]
        if s['states'].strip(): options['states']=s['states']
        for key,value in options.items(): command+=['--'+key,str(value)]
        audit_command=['singularity','exec','--cleanenv','--env','OPENBLAS_NUM_THREADS=2,OMP_NUM_THREADS=2,MKL_NUM_THREADS=2',
                       '--bind','/scicomp',str(root/'foodnet.sif'),'Rscript','--vanilla',str(scripts/auditor.name),
                       str(work),str(work/'saved_fit_validation.json')]
        job['command']=command;job['audit_command']=audit_command;job['task']=work.name
        script='#!/bin/bash\nset -uo pipefail\nstatus=0\n'
        script+=' '.join(q(v) for v in command)+' > '+q(str(work/'fit.log'))+' 2>&1 || status=$?\n'
        script+='printf "%s\\n" "$status" > '+q(str(work/'exit_status.txt'))+'\n'
        script+='if [ "$status" -eq 0 ]; then\n  audit_status=0\n'
        script+='  rm -f '+q(str(work/'saved_fit_validation.json'))+'\n'
        script+='  '+' '.join(q(v) for v in audit_command)+' > '+q(str(work/'audit.log'))+' 2>&1 || audit_status=$?\n'
        script+='  printf "%s\\n" "$audit_status" > '+q(str(work/'audit_exit_status.txt'))+'\n'
        script+='else\n  printf "%s\\n" "NOT_RUN_FIT_FAILED" > '+q(str(work/'audit_exit_status.txt'))+'\nfi\n'
        script+='exit "$status"\n'
        (work/'run.sh').write_text(script)
    (dest/'manifest.json').write_text(json.dumps(dict(jobs=jobs,source_sha256=hashes,original_outputs_preserved=True,
       pending_review=['Early-year parasite catchment/exposure conventions','Statistical review before dashboard replacement'],
       sampler_tuning='Feature-source corrections use adapt_delta=0.999 for every selected fit, including any original feature fit previously run at 0.99; six chains, 10001 iterations and the state formula/priors are retained. Original combined-source fits use 0.99.',
       crypto='Already corrected separately; not refitted'),indent=2)+'\n')
    (dest/'array.sh').write_text('#!/bin/bash\nset -euo pipefail\nprintf -v task "task_%02d" "$SGE_TASK_ID"\nbash '+q(str(dest))+'/"$task"/run.sh\n')
    (dest/'collect.sh').write_text('#!/bin/bash\nset -euo pipefail\npython3 '+q(str(dest/'collect.py'))+' '+q(str(dest))+'\n')
    return ['qsub','-terse','-V','-cwd','-S','/bin/bash','-N','foodnet_surveillance','-t','1-'+str(len(jobs)),'-pe','smp','12','-l',
            'h_rt=48:00:00,h_rss=53248M,mem_free=53248M,h_vmem=68G','-j','y','-o',str(dest/'array.log'),str(dest/'array.sh')]

def main():
    root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',action='append',help='Saved spline_results directory; repeat to scan multiple sources')
    p.add_argument('--clean-file');p.add_argument('--data-dir',default='/scicomp/groups-pure/EDEB/foodnet/trends/data');p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
    sources=[Path(v).resolve() for v in a.source] if a.source else [root/v for v in DEFAULT_SOURCES]
    data=Path(a.data_dir).resolve();clean=Path(a.clean_file).resolve() if a.clean_file else root/'output/20260911_140750/preprocessed/clean_mmwr.csv'
    if not a.prepare_only:
        for tool in ('qsub','singularity'):
            if not shutil.which(tool): p.error('Load module for '+tool)
        for f in [root/'foodnet.sif',clean]+[data/v for v in ('mmwr9625.sas7bdat','cen9625.sas7bdat','cen9625_para.sas7bdat')]:
            if not f.is_file(): p.error('Missing '+str(f))
    dest=root/'output'/('surveillance_refits_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    try: command=prepare(root,dest,data,sources,clean)
    except (ValueError,KeyError,OSError) as e: p.error(str(e))
    print('Output: '+str(dest),flush=True)
    print('Affected models: '+str(len(json.loads((dest/'manifest.json').read_text())['jobs'])),flush=True)
    if a.prepare_only:return
    job=subprocess.check_output(command,universal_newlines=True).strip();jid=job.split('.')[0]
    collect=subprocess.check_output(['qsub','-terse','-V','-cwd','-S','/bin/bash','-N','foodnet_surv_collect','-hold_jid',jid,'-pe','smp','1','-l','h_rt=01:00:00,h_rss=4096M,mem_free=4096M,h_vmem=8G','-j','y','-o',str(dest/'collection.log'),str(dest/'collect.sh')],universal_newlines=True).strip()
    print('Fit array: '+job+'\nCollection job: '+collect+'\nFinal log: '+str(dest/'collection.log')+'\nArchive: '+str(dest)+'.tar.gz')
if __name__=='__main__':main()
