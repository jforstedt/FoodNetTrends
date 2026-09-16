"""Strict expansion report validation; saved-fit rescoring can keep fits at source."""
import csv
import math
import re
from regional_audit_runtime import read, sha

def validate_reports(work,t,require_fit=True):
    if (require_fit and not (work/'fit_INTERNAL.rds').is_file()) or not (work/'heldout_truth_INTERNAL.csv').is_file():raise ValueError('Missing internal checkpoint')
    if (work/'reports/status.txt').read_text().strip()!='COUNTY_COVARIATE_EXPERIMENT_COMPLETE':raise ValueError('Incomplete R report')
    settings=read(work/'reports/experiment_settings.json')
    for key in ('task_id','pathogen','cutoff','temporal','local_seasonality','weather','age','weather_window','seed','draws_per_stream'):
        if settings.get(key)!=t[key]:raise ValueError('Changed report identity '+key)
    if settings.get('weather_mode')!='historical_conditional' or settings.get('scientific_acceptance') is not False:raise ValueError('Changed scientific status')
    states={'CA','CO','CT','GA','MD','MN','NM','NY','OR','TN'};years=set(range(t['cutoff']+1,t['cutoff']+4))
    parsed={}
    for name,ss in [('stream_scores.csv',states),('aggregate_tails.csv',states|{'ALL'})]:
        with (work/'reports'/name).open() as f:rows=list(csv.DictReader(f))
        expected={(state,year,k) for state in ss for year in years for k in range(5)}
        if len(rows)!=len(expected) or {(r['state'],int(r['year']),int(r['stream'])) for r in rows}!=expected:raise ValueError('Incomplete report domain '+name)
        if any(int(r['draws'])!=(4000 if int(r['stream'])==0 else 1000) for r in rows):raise ValueError('Wrong draw count')
        parsed[name]=rows
    def finite(r,key):
        v=float(r[key])
        if not math.isfinite(v):raise ValueError('Nonfinite metric '+key)
        return v
    for r in parsed['stream_scores.csv']:
        finite(r,'mean_log_score')
        if finite(r,'max_cell_density_relative_mcse')<0:raise ValueError('Negative MC error')
    for r in parsed['aggregate_tails.csv']:
        for key in ('observed','mean_expected','median_expected','p975_expected','max_expected','lower95','median_predictive','upper95'):
            if finite(r,key)<0:raise ValueError('Negative count summary')
        if not float(r['lower95'])<=float(r['median_predictive'])<=float(r['upper95']):raise ValueError('Unordered predictive interval')
        if not float(r['median_expected'])<=float(r['p975_expected'])<=float(r['max_expected']):raise ValueError('Unordered expected tail')
        for key in ('top_one_percent_mean_share','prob_above_twice_observed'):
            if not 0<=finite(r,key)<=1:raise ValueError('Invalid probability')
    for year in years:
        for k in range(5):
            parts=[r for r in parsed['aggregate_tails.csv'] if int(r['year'])==year and int(r['stream'])==k]
            total=next(r for r in parts if r['state']=='ALL');sites=[r for r in parts if r['state']!='ALL']
            for field in ('observed','mean_expected'):
                if not math.isclose(float(total[field]),sum(float(r[field]) for r in sites),rel_tol=1e-9,abs_tol=1e-8):raise ValueError('State/catchment totals differ')
    with (work/'reports/rng_protocol.csv').open() as f:rng=list(csv.DictReader(f))
    if len(rng)!=1:raise ValueError('Missing RNG protocol')
    for key,value in dict(protocol='explicit_config_v2',base_seed=str(t['seed']),stream_stride='50000',batch_size='100',r_configuration_seed_offset='20000',predictive_seed_offset='10000',inla_version='26.8.7').items():
        if rng[0].get(key)!=value:raise ValueError('RNG protocol differs '+key)
    for name in ('aggregate_draws_INTERNAL.rds','pooled_cell_scores_INTERNAL.csv','shape_streams.csv','settings.csv','input_checksums.csv','experiment_input_checksums.csv'):
        if not (work/'reports'/name).is_file() or not (work/'reports'/name).stat().st_size:raise ValueError('Missing '+name)
    if re.search(r'vb[.]correction[^\n]*aborted',(work/'task.log').read_text(errors='replace'),re.I):raise ValueError('Aborted variational correction')
    return sha(work/'heldout_truth_INTERNAL.csv')
