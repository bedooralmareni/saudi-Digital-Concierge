"""M5 v6 offline evaluator (strict clarification no-search gate). Gold is loaded ONLY inside evaluate_experiment().
Primary endpoint: success of the structured response contract, not prose truth.
Full prose/intent E2E is separately available after an explicit evidence-based review.
"""
import copy,csv,hashlib,json,math,sqlite3,statistics
from pathlib import Path
from collections import Counter,defaultdict
from jsonschema import Draft202012Validator
from m5_contract import FLAGS,FACT_TYPES,canonical_city,VERSION

TABLES={'hotel':('hotels','hotel_id'),'activity':('entertainment','entertainment_id'),
        'restaurant':('places','place_id'),'event':('events','event_id')}
STATUS={'MATCH':{'complete'},'NO_MATCH':{'no_match'},'COVERAGE_GAP':{'coverage_gap'},
        'INSUFFICIENT_DATA':{'insufficient_data'},'CLARIFY':{'needs_clarification','conflicting'},'PARTIAL':{'partial'}}
# Evaluator-only requirements transcribed from the frozen question texts.
REQUIRED={
 'SDC-001':{'activity':['genre','rating']},'SDC-003':{'activity':['genre','rating']},
 'SDC-007':{'hotel':['max_persons','guest_rating']},
 'SDC-008':{'hotel':['max_persons','guest_rating','star_rating']},
 'SDC-009':{'hotel':['max_persons','guest_rating','free_cancellation']},
 'SDC-014':{'hotel':['max_persons','star_rating','breakfast_included']},
 'SDC-019':{'hotel':['max_persons'],'activity':['genre','rating']},
 'SDC-020':{'hotel':['max_persons'],'activity':['genre','rating']},
 'SDC-025':{'hotel':['max_persons'],'event':[]},'SDC-027':{'hotel':['max_persons'],'event':[]},
 'SDC-031':{'restaurant':['categories','average_rating','rate_count']},
 'SDC-035':{'restaurant':['categories','average_rating','rate_count']},
 'SDC-037':{'event':[]},'SDC-038':{'event':['is_family_allowed']},
 'SDC-043':{},'SDC-045':{},'SDC-048':{},'SDC-055':{},'SDC-056':{},
 'SDC-058':{'hotel':['max_persons']}}
METRICS=['e2e_structured','component_completion','retrieval_evidence_coverage',
         'schema_validity','tool_syntax_validity','tool_error_rate','redundant_call_rate',
         'structured_unsupported_rate','e2e_reviewed','seconds','generation_seconds',
         'tool_calls','model_calls','total_tokens']
def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def file_hash(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ratio(n,d):return n/d if d else None
def write_json(path,obj):Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def write_csv(path,rows):
    if not rows:return
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def record(conn,kind,rid):
    table,col=TABLES[kind];r=conn.execute(f'SELECT * FROM {table} WHERE {col}=?',[rid]).fetchone()
    if r is None:return None
    r=dict(r)
    if kind=='restaurant' and r.get('granular_category')!='restaurants':return None
    for f in FLAGS:
        if r.get(f) is not None:r[f]=bool(r[f])
    return r

def empty_evidence(case,component,trace):
    """A zero-result search must match ALL requested no-match predicates, without extra filters."""
    sid=case['scenario_id']
    if component=='hotel' and sid=='SDC-043':
        name='search_hotels';required={'city':'Abha','guests':2,'max_price_sar':30}
        optional={'price_operator':'lte'};paging={'limit'}
    elif component=='restaurant' and sid in ('SDC-045','SDC-058'):
        name='search_places';required={'city':'Jeddah','entity_type':'restaurant'}
        optional={'semantic':False,'query':''};paging={'top_k'}
    else:return False
    for t in trace:
        if t.get('name')!=name or t.get('status')!='completed' or t.get('result')!=[]:continue
        a=copy.deepcopy(t.get('arguments') or {})
        a['city']=canonical_city(a.get('city'),{'أبها':'Abha','ابها':'Abha','جدة':'Jeddah','جده':'Jeddah'})
        if a.get('entity_type')=='restaurants':a['entity_type']='restaurant'
        if 'max_price_per_night' in a and 'max_price_sar' not in a:a['max_price_sar']=a.pop('max_price_per_night')
        if any(a.get(k)!=v for k,v in required.items()):continue
        if any(k not in required and k not in optional and k not in paging for k in a):continue
        # semantic order does not alter membership when query is empty.
        if 'price_operator' in a and a['price_operator']!='lte':continue
        if a.get('query','')!='':continue
        return True
    return False

def score_attempt(run,case,schema,conn,tool_schemas,snapshot,review=None):
    obj=run.get('response');trace=run.get('trace',[]);errors=[];failures=[]
    validator=Draft202012Validator(schema)
    errors=[f"{'/'.join(map(str,e.absolute_path))}: {e.message}" for e in validator.iter_errors(obj)]
    if not errors and (obj['scenario_id']!=case['scenario_id'] or obj['language']!=case['language'].lower()):errors=['Identity/language field mismatch']
    valid=not errors
    finished=run.get('status')=='completed'
    if not finished:failures.append(run.get('status','execution_error'))
    if errors:failures.append('invalid_output_contract')
    items=(obj['recommendations']+[i for d in obj['days'] for i in d['items']]) if valid else []
    retrieved={(r.get('entity_type'),r['record_id']) for t in trace if t.get('status')=='completed' and isinstance(t.get('result'),list)
               for r in t['result'] if isinstance(r,dict) and r.get('record_id')}
    claims=bad=0;item_errors={};required_errors={}
    for item in items:
        kind=item['entity_type'];rid=item['record_id'];row=record(conn,kind,rid);problems=[];missing=[]
        claims+=1
        if row is None:bad+=1;problems.append('nonexistent_record')
        checks={'name':'name','city':'city','recorded_hotel_price_sar':'price_sar',
                'hotel_price_snapshot_date':'snapshot_date','event_start_date':'start_date','event_end_date':'end_date'}
        for outfield,dbfield in checks.items():
            value=item[outfield]
            if value is None:continue
            claims+=1
            applicable=outfield in ('name','city') or (kind=='hotel' and 'hotel' in outfield) or (kind=='event' and outfield.startswith('event_'))
            expected=snapshot if outfield=='hotel_price_snapshot_date' else row.get(dbfield) if row else None
            if not row or not applicable or value!=expected:bad+=1;problems.append(outfield)
        relevant={'hotel':{'max_persons','guest_rating','star_rating','breakfast_included','free_cancellation'},
                  'activity':{'genre','rating'},'restaurant':{'categories','average_rating','rate_count'},'event':{'is_family_allowed'}}[kind]
        for field,value in item['facts'].items():
            if value is None:continue
            claims+=1
            if not row or field not in relevant or value!=row.get(field):bad+=1;problems.append('facts.'+field)
        for field in REQUIRED[case['scenario_id']].get(kind,[]):
            if item['facts'].get(field) is None:missing.append('facts.'+field)
        if kind=='hotel':
            for field in ('recorded_hotel_price_sar','hotel_price_snapshot_date'):
                if item[field] is None:missing.append(field)
        if kind=='event' and row:
            for outfield,dbfield in [('event_start_date','start_date'),('event_end_date','end_date')]:
                if item[outfield]!=row[dbfield]:missing.append(outfield)
        item_errors[(kind,rid)]=problems;required_errors[(kind,rid)]=missing
    statuses=valid and obj['status'] in STATUS[case['expected_status']]
    if not statuses:failures.append('wrong_status')
    codes=set(obj['issue_codes']) if valid else set()
    components=[]
    for c in case['components'] or [{'component':'request_logic','mode':'clarify'}]:
        kind=c['component'];selected=[i for i in items if i['entity_type']==kind]
        ids={i['record_id'] for i in selected};mode=c['mode'];evidence=False;gate=False
        if mode=='recommend':
            accepted=set(c['accepted_ids']);groups=[set(g) for g in c['distinct_option_groups']]
            candidate_ids={rid for k,rid in retrieved if k==kind}
            evidence=sum(bool(g&candidate_ids) for g in groups)>=c['required_count']
            gate=(len(selected)==len(ids)==c['required_count'] and ids<=accepted
                and sum(bool(g&ids) for g in groups)==c['required_count']
                and all((kind,rid) in retrieved for rid in ids)
                and all(not item_errors[(kind,rid)] and not required_errors[(kind,rid)] for rid in ids))
        elif mode=='no_match':
            evidence=empty_evidence(case,kind,trace)
            code='restaurant_coverage_gap' if kind=='restaurant' else 'no_match'
            gate=not selected and evidence and code in codes
        elif mode=='unknown':
            evidence=any((kind,str(rid)) in retrieved for rid in c['supporting_ids'])
            lookup=obj.get('lookup') if valid else None
            gate=(not selected and evidence and isinstance(lookup,dict)
                and lookup=={'record_id':'hotels_00007','field':'breakfast_included','value':None}
                and 'unknown_field' in codes)
        else:
            target='city' if case['scenario_id']=='SDC-055' else 'budget'
            expected_code='missing_city' if target=='city' else 'conflicting_budget'
            evidence=not trace # Clarification requires no database access in these two cases.
            gate=(valid and not items and obj['response_type']=='clarification'
                  and obj['clarification_target']==target and expected_code in codes
                  and any(q.strip() for q in obj['clarifying_questions']) and not trace)
        components.append({'component':kind,'mode':mode,'passed':bool(finished and valid and gate),
                           'retrieval_evidence_pass':bool(evidence)})
    shape=False;consistency=False
    if valid:
        kinds={i['entity_type'] for i in items}
        allowed_kinds={c['component'] for c in case['components'] if c['mode']=='recommend'}
        shape=(not(obj['recommendations'] and obj['days']) and kinds<=allowed_kinds)
        if obj['days']:
            shape=shape and obj['response_type']=='itinerary' and len(obj['days'])==1 and obj['days'][0]['day_number']==1 and obj['days'][0]['date'] is None
        elif items:shape=shape and obj['response_type']=='recommendations'
        elif case['expected_status']=='CLARIFY':shape=shape and obj['response_type']=='clarification'
        elif case['expected_status']=='INSUFFICIENT_DATA':shape=shape and obj['response_type']=='information'
        consistency=(len({(i['entity_type'],i['record_id']) for i in items})==len(items)
            and bool(obj['message'].strip()) and all(i['reason'].strip() for i in items)
            and obj['costs']['verified_trip_total_sar'] is None
            and all((k,rid) in retrieved for k,rid in [(i['entity_type'],i['record_id']) for i in items]))
        if case['expected_status']!='CLARIFY':consistency=consistency and obj['clarification_target'] is None
        if case['expected_status']!='INSUFFICIENT_DATA':consistency=consistency and obj['lookup'] is None
        if obj['status']=='complete':consistency=consistency and not obj['clarifying_questions'] and all(c['result']=='met' for c in obj['constraint_results'])
        if any(i['entity_type']=='hotel' for i in items):consistency=consistency and 'historical_hotel_price' in codes
        if any(i['entity_type']=='event' for i in items):consistency=consistency and 'historical_event_dates' in codes
        allowed_codes=set()
        if 'hotel' in kinds:allowed_codes.add('historical_hotel_price')
        if 'event' in kinds:allowed_codes.add('historical_event_dates')
        behavior_codes={'NO_MATCH':{'no_match'},'COVERAGE_GAP':{'restaurant_coverage_gap'},
            'INSUFFICIENT_DATA':{'unknown_field'},'PARTIAL':{'restaurant_coverage_gap'},
            'CLARIFY':{'missing_city'} if case['scenario_id']=='SDC-055' else {'conflicting_budget'}}
        allowed_codes.update(behavior_codes.get(case['expected_status'],set()))
        consistency=consistency and codes<=allowed_codes
        # Cost fields are optional, but any supplied value must match one chosen hotel.
        cost=obj['costs'];hotel_prices={i['recorded_hotel_price_sar'] for i in items if i['entity_type']=='hotel'}
        for field in ('recorded_hotel_price_sar','hotel_price_snapshot_date'):
            if cost[field] is not None:
                claims+=1;ok=(cost[field] in hotel_prices if field=='recorded_hotel_price_sar' else bool(hotel_prices) and cost[field]==snapshot)
                if not ok:bad+=1;consistency=False
        trace_ids={rid for _,rid in retrieved}
        if any(not set(c['evidence_ids'])<=trace_ids for c in obj['constraint_results']):consistency=False
    if any(item_errors.values()):failures.append('incorrect_structured_fact')
    if any(required_errors.values()):failures.append('missing_requested_fact')
    if not all(c['passed'] for c in components):failures.append('component_failure')
    if not shape:failures.append('response_shape')
    if not consistency:failures.append('structured_inconsistency')
    syntax=errors_tool=redundant=0;seen=set();action_rows=[]
    for t in trace:
        name=t.get('name');a=t.get('arguments');ok=name in tool_schemas and isinstance(a,dict)
        if ok:ok=not list(Draft202012Validator(tool_schemas[name]).iter_errors(a))
        try:ok=ok and json.loads(t.get('raw_arguments','null'))==a
        except (ValueError,TypeError):ok=False
        syntax+=bool(ok);key=digest([name,a]);repeat=key in seen
        redundant+=repeat;seen.add(key)
        errors_tool+=t.get('status')!='completed'
        action_rows.append({'call_id':t.get('call_id'),'syntax_valid':bool(ok),'repeated':repeat})
    e2e=int(finished and valid and statuses and shape and consistency and bad==0 and all(c['passed'] for c in components))
    reviewed=None;review_complete=False
    if review:
        checks=['language_pass','required_text_and_behavior_pass','all_text_claims_supported','intent_and_consistency_pass']
        for field in checks:
            if review.get(field) is not None and type(review[field]) is not bool:raise ValueError('Review decisions must be boolean or null')
        review_complete=all(type(review.get(k)) is bool for k in checks) and bool(str(review.get('reviewer','')).strip()) and bool(str(review.get('evidence_notes','')).strip())
        if review_complete:reviewed=int(bool(e2e) and all(review[k] for k in checks))
    usage=run.get('usage_totals') or {}
    return {'attempt_id':run['attempt_id'],'run_id':run['run_id'],'scenario_id':case['scenario_id'],
        'language':case['language'],'scenario_type':case['scenario_type'],'domain':case['domain'],
        'execution_status':run.get('status'),'schema_validity':int(valid),'e2e_structured':e2e,
        'component_completion':sum(c['passed'] for c in components)/len(components),
        'retrieval_evidence_coverage':sum(c['retrieval_evidence_pass'] for c in components)/len(components),
        'tool_syntax_validity':ratio(syntax,len(trace)),'tool_error_rate':ratio(errors_tool,len(trace)),
        'redundant_call_rate':ratio(redundant,len(trace)),
        'structured_unsupported_rate':ratio(bad,claims),'structured_claims':claims,'unsupported_claims':bad,
        'valid_tool_calls':syntax,'error_tool_calls':errors_tool,'redundant_tool_calls':redundant,
        'e2e_reviewed':reviewed,'review_complete':review_complete,'seconds':run.get('elapsed_seconds'),
        'generation_seconds':run.get('generation_seconds'),'tool_calls':len(trace),'model_calls':len(run.get('model_calls',[])),
        'total_tokens':usage.get('total_tokens'),'elapsed_seconds_is_partial':run.get('elapsed_seconds_is_partial',False),
        'retrieval_transition':run.get('retrieval_transition'),'protocol_warnings':run.get('protocol_warnings',[]),
        'components':components,'actions':action_rows,'schema_errors':errors,'failures':sorted(set(failures)),
        'missing_facts':{f'{k[0]}:{k[1]}':v for k,v in required_errors.items() if v},
        'incorrect_facts':{f'{k[0]}:{k[1]}':v for k,v in item_errors.items() if v}}

def summarize(scores,cases,seeds):
    expected={c['scenario_id'] for c in cases};rows=[];summaries=[]
    for metric in METRICS:
        means=[]
        for seed in seeds:
            batch=[s for s in scores if s['run_id']==seed];complete={s['scenario_id'] for s in batch}==expected
            vals=[s[metric] for s in batch if s.get(metric) is not None and not(metric in ('seconds','generation_seconds') and s['elapsed_seconds_is_partial'])]
            numerator=denominator=None
            if metric in ('tool_syntax_validity','tool_error_rate','redundant_call_rate'):
                key={'tool_syntax_validity':'valid_tool_calls','tool_error_rate':'error_tool_calls','redundant_call_rate':'redundant_tool_calls'}[metric]
                numerator=sum(s[key] for s in batch);denominator=sum(s['tool_calls'] for s in batch);value=ratio(numerator,denominator)
            elif metric=='structured_unsupported_rate':
                numerator=sum(s['unsupported_claims'] for s in batch);denominator=sum(s['structured_claims'] for s in batch);value=ratio(numerator,denominator)
            else:value=statistics.mean(vals) if vals else None
            metric_complete=complete and value is not None
            if metric in ('e2e_reviewed','seconds','generation_seconds','total_tokens'):metric_complete=metric_complete and len(vals)==len(batch)
            rows.append({'metric':metric,'run_id':seed,'expected_cases':len(expected),'attempted_cases':len(batch),
                         'scored_cases':len(vals),'complete_run':complete,'metric_complete':metric_complete,
                         'numerator':numerator,'denominator':denominator,'score':value})
            if metric_complete:means.append(value)
        all_done=len(means)==len(seeds)
        summaries.append({'metric':metric,'runs_scored':len(means),'runs_expected':len(seeds),
                          'mean':statistics.mean(means) if all_done else None,
                          'sample_variance':statistics.variance(means) if all_done else None,
                          'sample_sd':statistics.stdev(means) if all_done else None})
    return rows,summaries

def evaluate_experiment(project,folder,review_path=None):
    project=Path(project);folder=Path(folder);manifest=json.loads((folder/'experiment_manifest.json').read_text())
    cfg=manifest['config'];frozen=json.loads((folder/'frozen20.json').read_text())
    if manifest['config_sha256']!=digest(cfg) or digest(frozen)!=cfg['benchmark_sha256']:raise ValueError('Manifest/benchmark hash mismatch')
    if cfg['contract_version']!=VERSION:raise ValueError('Wrong contract version')
    for rel,h in cfg['source_hashes'].items():
        if file_hash(project/rel)!=h:raise ValueError('Source mismatch: '+rel)
    for name,h in cfg['module_hashes'].items():
        if file_hash(Path(__file__).parent/name)!=h:raise ValueError('Evaluator/module mismatch: '+name)
    gold=json.loads((project/'evaluation/scenario_package/development/gold.json').read_text())
    byid={c['scenario_id']:c for c in gold};cases=frozen['cases'];seeds=frozen['run_ids']
    mode=cfg.get('run_mode','development20')
    expected_count={'smoke5':5,'development20':20}.get(mode)
    if expected_count is None or len(cases)!=expected_count or len({c['scenario_id'] for c in cases})!=expected_count or seeds!=[17,29,43]:raise ValueError('Expected smoke5 or development20 with seeds 17/29/43')
    if not {c['scenario_id'] for c in cases} <= set(REQUIRED):raise ValueError('Unsupported scenarios: extend evaluator and validate gold before another split')
    for c in cases:
        if c['prompt']!=byid[c['scenario_id']]['prompt'] or c['language']!=byid[c['scenario_id']]['language']:raise ValueError('Gold/prompt mismatch')
    reviews={}
    if review_path and Path(review_path).exists():
        entries=json.loads(Path(review_path).read_text())
        for r in entries:
            if r['attempt_id'] in reviews:raise ValueError('Duplicate review')
            reviews[r['attempt_id']]=r
    runs=[json.loads(p.read_text()) for p in sorted((folder/'attempts').glob('*.json'))]
    keys=set();attempt_ids=set();scores=[];templates=[];queue=[]
    db=project/'data/final/knowledge_base.sqlite'
    if file_hash(db)!=cfg['database_sha256']:raise ValueError('Database mismatch')
    conn=sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True);conn.row_factory=sqlite3.Row
    tool_schemas={t['function']['name']:t['function']['parameters'] for t in cfg['tools']}
    try:
        for r in runs:
            key=(r['run_id'],r['scenario_id'])
            if key in keys or r['attempt_id'] in attempt_ids:raise ValueError('Duplicate attempt')
            keys.add(key);attempt_ids.add(r['attempt_id'])
            if r['run_id'] not in seeds or r['scenario_id'] not in {c['scenario_id'] for c in cases}:raise ValueError('Unplanned attempt')
            if r['config_sha256']!=manifest['config_sha256'] or r['database_sha256']!=cfg['database_sha256']:raise ValueError('Mixed experiment')
            case=byid[r['scenario_id']]
            if r['request']!=case['prompt'] or r['status']=='started':raise ValueError('Changed prompt or active unfinished attempt; reconcile interruption first')
            review=reviews.get(r['attempt_id'])
            if review and (review['scenario_id']!=r['scenario_id'] or review['run_id']!=r['run_id']):raise ValueError('Review identity mismatch')
            scores.append(score_attempt(r,case,cfg['schema'],conn,tool_schemas,cfg['snapshot']['hotel_snapshot_date'],review))
            templates.append({'attempt_id':r['attempt_id'],'scenario_id':r['scenario_id'],'run_id':r['run_id'],
                'reviewer':'','language_pass':None,'required_text_and_behavior_pass':None,
                'all_text_claims_supported':None,'intent_and_consistency_pass':None,'evidence_notes':''})
            queue.append({'attempt_id':r['attempt_id'],'question':case['prompt'],'expected_behavior':case['behavior'],
                          'gold_components':case['components'],'response':r.get('response'),'raw_answer':r.get('raw_answer'),'trace':r['trace']})
    finally:conn.close()
    out=folder/'m5_results';out.mkdir(exist_ok=True)
    write_json(out/'scores.json',scores);write_json(out/'review_queue.json',queue)
    # Preserve existing review decisions; append newly collected attempts after resume.
    review_file=folder/'human_review.json'
    existing=json.loads(review_file.read_text()) if review_file.exists() else []
    known={r['attempt_id'] for r in existing}
    existing.extend(t for t in templates if t['attempt_id'] not in known)
    write_json(review_file,existing)
    run_rows,summary=summarize(scores,cases,seeds)
    write_csv(out/'run_scores.csv',run_rows);write_csv(out/'summary.csv',summary)
    write_csv(out/'scores.csv',[{k:v for k,v in s.items() if not isinstance(v,(dict,list))} for s in scores])
    failures=[{'scenario_id':s['scenario_id'],'run_id':s['run_id'],'e2e_structured':s['e2e_structured'],
               'failure_categories':'; '.join(s['failures']),'missing_facts':json.dumps(s['missing_facts'],ensure_ascii=False),
               'incorrect_facts':json.dumps(s['incorrect_facts'],ensure_ascii=False)} for s in scores]
    write_csv(out/'failure_analysis.csv',failures)
    write_csv(out/'diagnostics.csv',[{'scenario_id':r['scenario_id'],'seed':r['run_id'],
        'execution_status':r['status'],'retrieval_transition':r.get('retrieval_transition'),
        'protocol_warnings':'; '.join(r.get('protocol_warnings',[])),
        'final_calls':sum(c['phase']=='final' for c in r.get('model_calls',[])),
        'tool_calls':len(r['trace']),'tool_errors':sum(t.get('status')!='completed' for t in r['trace']),
        'schema_errors':'; '.join(r.get('validation_errors',[]))} for r in runs])
    counts=Counter(f for s in scores for f in s['failures'])
    write_csv(out/'failure_categories.csv',[{'category':k,'attempts':v,'rate_of_attempts':v/len(scores)} for k,v in counts.most_common()])
    slices=[]
    for field in ('language','scenario_type','domain'):
        for value in sorted({s[field] for s in scores}):
            ss=[s for s in scores if s[field]==value]
            slices.append({'group':field,'value':value,'attempts':len(ss),'unique_cases':len({s['scenario_id'] for s in ss}),
                           'e2e_structured':statistics.mean(s['e2e_structured'] for s in ss),
                           'component_completion':statistics.mean(s['component_completion'] for s in ss)})
    write_csv(out/'subgroup_results.csv',slices)
    complete=keys=={(seed,c['scenario_id']) for seed in seeds for c in cases}
    readiness={'expected_attempts':len(cases)*len(seeds),'run_mode':mode,'m5_minimum_case_count_met':len(cases)>=20,'recorded_attempts':len(runs),'all_attempts_recorded':complete,
        'three_actual_seeds':cfg['seeds'],'source_split':'Development',
        'automatic_report_ready':complete and mode=='development20','diagnostic_report_ready':complete,
        'full_prose_review_ready':complete and mode=='development20' and all(s['review_complete'] for s in scores),
        'human_reviews_completed':sum(s['review_complete'] for s in scores),
        'not_attempted':[f'{seed}_{sid}' for seed,sid in sorted({(seed,c['scenario_id']) for seed in seeds for c in cases}-keys)],
        'scope':'Automatic metrics evaluate the explicit structured output contract. Prose truth and semantic intent require human_review.json.',
        'infrastructure_failures':sum(s['execution_status'] in ('execution_error','interrupted','context_limit','oom','timeout') for s in scores),
        'gpu_validation':'These are locally recorded experiment results; notebook delivery itself contains no GPU result.'}
    write_json(out/'readiness.json',readiness)
    lines=['# M5 — Qwen3-8B single-agent', '',f'Experiment: {folder.name}',
           f'Recorded attempts: {len(runs)}/{len(cases)*len(seeds)}. Split: Development; mode: {mode}; unique cases: {len(cases)}. Seeds: {seeds}.',
           'Primary endpoint: structured task success; full narrative claims are not included without the review.',
           '', '| Metric | Mean | Sample SD across seed means | Sample variance |','|---|---:|---:|---:|']
    for s in summary:
        fmt=lambda x:'Pending / not applicable' if x is None else f'{x:.6f}'
        lines.append('| '+s['metric']+' | '+' | '.join(fmt(s[k]) for k in ('mean','sample_sd','sample_variance'))+' |')
    lines+=['','## Failure analysis',*[f'- {k}: {v} attempts' for k,v in counts.most_common()],
        '', '## Reporting limits',
        '- Development results do not establish untouched-test generalization.',
        f'- {len(runs)} attempts on {len(cases)} cases are not independent tasks; SD is across three seed-level scores.',
        '- Quantized GPU sampling is seeded but bitwise identity across different hardware/software is not guaranteed.',
        '- Historical database records do not establish current availability or live prices.',
        '- v5 vs v4 updates the system/final prompts only, with unchanged scoring logic, generation settings, one-pass JSON repair and tools. The earlier v3-v4 comparison was not a prompt-only ablation. Old OpenAI v1 results are not a controlled architecture comparison.',
        '- smoke5 is diagnostic only and does not meet the 20-case M5 requirement. Validation and Final Test need separately validated requirements and are not supported by this evaluator.',
        '- Local GPU monetary cost is unpriced. Latency includes model/tools/checkpoint overhead; generation_seconds excludes model loading.',
        '- No failed attempt is silently retried or omitted; infrastructure errors are separately identified.',
        '', '## Human review',f"Completed: {readiness['human_reviews_completed']}/{len(cases)*len(seeds)}. Fill human_review.json with evidence notes and rerun the offline evaluation cell.",
        'Do not describe structured_unsupported_rate as the hallucination rate of the complete prose answer.']
    (out/'M5_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    return readiness,summary
