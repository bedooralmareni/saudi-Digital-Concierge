"""Score the fixed Development20 benchmark offline.

Run with Python 3 and jsonschema installed:
    python score_runs.py --project REPO --frozen frozen20.json \
        --runs openai/runs.jsonl qwen/runs.jsonl --out m5_scores

Both log files use the Frozen20 notebook's attempt schema. Each row carries
attempt_id, run_id, scenario_id, request, model, system, database_sha256,
status, response (or raw_answer), and trace. Pass one file to score one model.
The project directory must contain the pinned database, schemas and tools.
Gold stays in the evaluator process. Structured metrics are fully automatic;
the optional reviewed metrics also check free-text claims and semantic intent.
"""
import argparse, csv, hashlib, json, sqlite3, statistics
from pathlib import Path
from jsonschema import Draft202012Validator
from cost_from_runs import price_attempt, PRICING_DEFAULT

VERSION='1.2.0'
TABLES={'hotel':('hotels','hotel_id'),'restaurant':('places','place_id'),
        'activity':('entertainment','entertainment_id'),'event':('events','event_id')}
STATUS={'MATCH':['complete'],'NOT_ONGOING':['complete'],'NO_MATCH':['no_match'],
        'COVERAGE_GAP':['coverage_gap'],'INSUFFICIENT_DATA':['insufficient_data'],
        'CLARIFY':['needs_clarification','conflicting'],'PARTIAL':['partial']}
FIELDS={'name':'name','city':'city','recorded_hotel_price_sar':'price_sar',
        'hotel_price_snapshot_date':'snapshot_date','event_start_date':'start_date','event_end_date':'end_date'}

def rate(n,d):return n/d if d else None

def decision(d,key):
    v=d.get(key)
    if v is not None and type(v) is not bool:raise ValueError(f'{key} must be true/false/null')
    return v

def conjunction(values):
    return False if False in values else None if None in values else True

def read_record(conn,kind,rid):
    if kind not in TABLES:return None
    table,col=TABLES[kind]
    row=conn.execute(f'SELECT * FROM {table} WHERE {col}=?',(rid,)).fetchone()
    if row is None:return None
    row=dict(row)
    if kind=='restaurant' and row.get('granular_category')!='restaurants':return None
    return row

def evaluate(run,case,schema,conn,tool_schemas,review=None, hotel_snapshot_date=None, pricing=None):
    review=review or {}
    obj=run.get('response')
    errors=[]
    if obj is None:
        try:obj=json.loads(run.get('raw_answer') or '')
        except (ValueError,TypeError):errors=['Final answer is not JSON']
    if not errors:
        errors=[f'{list(e.absolute_path)}: {e.message}' for e in Draft202012Validator(schema).iter_errors(obj)]
    sv=not errors
    if sv and obj['scenario_id']!=case['scenario_id']:errors.append('scenario_id mismatch');sv=False
    estimate=price_attempt(run, pricing) if pricing is not None and run.get('api_calls') else {
        'estimated_cost_usd': run.get('cost_usd'), 'cost_status': 'logged_or_unpriced',
        'price_tier': None, 'price_source': None, 'costed_calls': None
    }
    out={'attempt_id':run['run_id'],'run_id':run.get('repetition_id'),'scenario_id':case['scenario_id'],'model':run.get('model'),
         'system':run.get('system'),'repetition_id':run.get('repetition_id'),
         'split':case['split'],'language':case['language'],'domain':case['domain'],
         'scenario_type':case['scenario_type'],'expected_status':case['expected_status'],
         'execution_status':run.get('status'),'schema_validity':int(sv),'schema_errors':errors,
         'seconds':run.get('elapsed_seconds'),'tokens':run.get('usage_totals'),
         'cost_usd':estimate['estimated_cost_usd'], 'cost_status':estimate['cost_status'],
          'cost_price_tier':estimate['price_tier'], 'cost_source':estimate['price_source'],
          'costed_calls':estimate['costed_calls'], 'components':[],'scorer_version':VERSION}
    items=(obj['recommendations']+[i for d in obj['days'] for i in d['items']]) if sv else []
    rec_components=[c for c in case['components'] if c['mode']=='recommend']
    allowed={(c['component'],rid) for c in rec_components for rid in c['accepted_ids']}
    compliant=sum((i['entity_type'],i['record_id']) in allowed for i in items)
    out.update(selected_options=len(items),compliant_options=compliant,
        hcs=rate(compliant,len(items)) if items else 0.0 if rec_components else None,
        all_options_compliant=bool(sv and (compliant==len(items))),
        status_matches=bool(sv and obj['status'] in STATUS[case['expected_status']]))
    checked=unsupported=grounded=0
    mismatches=[]
    for i in items:
        row=read_record(conn,i['entity_type'],i['record_id'])
        checked+=1
        if row is None:unsupported+=1;mismatches.append({'id':i['record_id'],'field':'record_id'})
        else:grounded+=1
        for field,col in FIELDS.items():
            value=i[field]
            if value is None:continue # omissions handled by completeness review
            checked+=1
            relevant=field in ['name','city'] or (field.startswith(('recorded_hotel','hotel_price')) and i['entity_type']=='hotel') or (field.startswith('event_') and i['entity_type']=='event')
            expected = hotel_snapshot_date if field == 'hotel_price_snapshot_date' else row.get(col) if row else None
            if row is None or not relevant or expected != value:
                unsupported+=1;mismatches.append({'id':i['record_id'],'field':field})
    out.update(entity_grounding=rate(grounded,len(items)),structured_claims_checked=checked,
               structured_claims_unsupported=unsupported,structured_ucr=rate(unsupported,checked),
               field_mismatches=mismatches)
    retrieved = {
        str(record['record_id'])
        for step in run.get('trace', [])
        if isinstance(step.get('result'), list)
        for record in step['result']
        if isinstance(record, dict) and record.get('record_id') is not None
    }
    search_tools = {
        'hotel': 'search_hotels', 'activity': 'search_places',
        'restaurant': 'search_places', 'event': 'search_events',
    }
    out['selected_ids_in_trace'] = all(i['record_id'] in retrieved for i in items)
    comps=case['components'] or [{'component':'request_logic','mode':'behavior','required_count':0}]
    for idx,c in enumerate(comps):
        selected=[i for i in items if i['entity_type']==c['component']]
        cr=(review.get('components') or {}).get(str(idx),{})
        if c['mode']=='recommend':
            ids=[i['record_id'] for i in selected]
            groups=c['distinct_option_groups']
            distinct=sum(bool(set(ids)&set(g)) for g in groups)
            gate=sv and len(ids)==c['required_count'] and distinct==c['required_count'] and all(x in c['accepted_ids'] for x in ids)
            # Price may be unknown or not requested; do not require the field
            # for every hotel. Required facts are checked in review rather than
            # treating an optional output field as a universal hard constraint.
            if gate and c['component'] == 'event':
                records = {str(r[c['id_field']]): r for r in c['evidence']}
                gate = all(
                    all(i[field] == records[i['record_id']].get(column)
                        for field, column in [('event_start_date', 'start_date'), ('event_end_date', 'end_date')])
                    for i in selected
                )
            if gate:
                gate = all(i['record_id'] in retrieved for i in selected)
                gate = gate and not any(x['id'] in ids for x in mismatches)
        else:
            gate = sv and not selected and out['status_matches']
            if gate and case['expected_status'] == 'CLARIFY':
                gate = obj['response_type'] == 'clarification' and any(
                    q.strip() for q in obj['clarifying_questions']
                )
            if gate and c['mode'] == 'unknown' and c.get('supporting_ids'):
                gate = bool(retrieved.intersection(map(str, c['supporting_ids'])))
            if gate and c['mode'] == 'no_match':
                gate = any(
                    step.get('name', step.get('tool')) == search_tools.get(c['component'])
                    and step.get('result') == []
                    for step in run.get('trace', [])
                )
        passed=conjunction([bool(gate),decision(cr,'required_facts_and_behavior_pass')])
        out['components'].append({'index':idx,'component':c['component'],'mode':c['mode'],
            'automated_gate':bool(gate),'passed':passed})
    flags=[c['passed'] for c in out['components']]
    out['cc_structured'] = sum(c['automated_gate'] for c in out['components']) / len(flags)
    out['cc_lower_bound']=sum(v is True for v in flags)/len(flags)
    out['cc']=out['cc_lower_bound'] if all(v is not None for v in flags) else None
    # Every attempted call remains in the denominator, including malformed/repeated calls.
    # A single identical retry after an actual tool error is allowed; otherwise
    # repeated calls consume tokens without new evidence and are flagged.
    seen={};actions=[];tool_errors=0
    for idx,t in enumerate(run.get('trace',[])):
        reasons=[];name=t.get('name',t.get('tool'));args=None
        try:
            args=json.loads(t['raw_arguments']) if 'raw_arguments' in t else t['arguments']
        except (ValueError,TypeError,KeyError):reasons.append('malformed_arguments')
        if name not in tool_schemas:reasons.append('unknown_tool')
        elif args is not None and list(Draft202012Validator(tool_schemas[name]).iter_errors(args)):reasons.append('invalid_arguments')
        key=json.dumps([name,args],sort_keys=True,ensure_ascii=False)
        result=t.get('result')
        is_error = isinstance(result, dict) and ('error' in result or 'error_type' in result)
        previous = seen.get(key, [])
        # Exactly one repeated call is allowed *only* if the first call failed.
        if previous and not (len(previous) == 1 and previous[0] is True):
            reasons.append('repeated_call')
        seen.setdefault(key, []).append(is_error)
        if not isinstance(result, list) and not is_error:
            reasons.append('missing_outcome')
        if isinstance(result,dict) and ('error' in result or 'error_type' in result):tool_errors+=1
        if isinstance(result,dict) and result.get('error_type') in ['InvalidArgumentsOrIndex','InvalidArguments','UnknownTool','RepeatedCall']:
            reasons.append('tool_rejected_call')
        if args is None or not isinstance(args,dict):reasons.append('arguments_not_object')
        ar=(review.get('actions') or {}).get(str(idx),{})
        # Reviewer checks intent, hard-constraint relaxation and permission/context.
        passed=conjunction([not reasons,decision(ar,'constraint_and_access_pass')])
        actions.append({'index':idx,'automatic_valid':not reasons,'reasons':reasons,'passed':passed})
    out['actions']=actions
    out['attempted_tool_calls']=len(actions)
    out['tool_error_rate']=rate(tool_errors,len(actions))
    out['tool_syntax_validity']=rate(sum(a['automatic_valid'] for a in actions),len(actions))
    out['tv']=rate(sum(a['passed'] is True for a in actions),len(actions)) if all(a['passed'] is not None for a in actions) else None
    out['unjustified_no_retrieval']=bool(rec_components and not any(isinstance(t.get('result'),list) for t in run.get('trace',[])))
    # Distinguish deterministic structured-response checks from semantic review.
    # This is not a replacement for a complete prose/intent audit.
    consistency_issues = []
    if sv:
        if obj['response_type'] == 'recommendations' and obj['days']:
            consistency_issues.append('unexpected_days_in_recommendation')
        if obj['response_type'] == 'itinerary' and obj['recommendations']:
            consistency_issues.append('flat_recommendations_in_itinerary')
        if obj['status'] == 'complete' and obj['clarifying_questions']:
            consistency_issues.append('complete_with_clarifying_questions')
        if obj['status'] in ('no_match', 'coverage_gap', 'needs_clarification', 'conflicting') and items:
            consistency_issues.append('no_result_status_with_recommendations')
        if obj['status'] == 'complete' and any(x['result'] == 'unmet' for x in obj['constraint_results']):
            consistency_issues.append('complete_with_unmet_constraint')
        if len({(i['entity_type'],i['record_id']) for i in items}) < len(items):
            consistency_issues.append('duplicate_recommendation_record_id')
    out['structured_consistency_pass'] = int(sv and not consistency_issues)
    out['structured_consistency_issues'] = consistency_issues
    prose=review.get('prose_claims')
    if prose is not None:
        for c in prose:
            if not c.get('claim') or type(c.get('supported')) is not bool or not c.get('evidence_note'):
                raise ValueError('Each prose claim needs claim, supported bool and evidence_note')
    reviewed=decision(review,'all_prose_claims_reviewed') is True
    if reviewed and prose is None:raise ValueError('Provide prose_claims, even if empty')
    total_checked=checked+(len(prose) if reviewed else 0)
    total_bad=unsupported+(sum(not c['supported'] for c in prose) if reviewed else 0)
    out['ucr']=rate(total_bad,total_checked) if reviewed else None
    out['consistency']=conjunction([bool(out['structured_consistency_pass']),decision(review,'consistency_pass')])
    automatic=sv and out['status_matches'] and compliant==len(items) and unsupported==0 and not out['unjustified_no_retrieval'] and run.get('status')=='completed'
    output_language_matches = sv and obj['language'] == case['language'].lower()
    # This baseline checks structured evidence; prose and semantic intent are audited separately.
    out['e2e_structured'] = int(
        automatic and output_language_matches and out['selected_ids_in_trace']
        and out['structured_consistency_pass'] and not obj['days'] and out['cc_structured'] == 1
        and bool(obj['message'].strip())
        and obj['costs']['verified_trip_total_sar'] is None
    )
    final=conjunction([bool(out['e2e_structured']),*flags,decision(review,'language_pass'),decision(review,'intent_shape_pass'),
                       out['consistency'],(total_bad==0 if reviewed else None)])
    out['e2e']=int(final) if final is not None else None
    out['e2e_lower_bound']=int(final is True)
    out['review_pending']=any(v is None for v in flags) or not reviewed or any(decision(review,k) is None for k in ['language_pass','intent_shape_pass','consistency_pass']) or any(a['passed'] is None for a in actions)
    return out

def template(run,case):
    return {'run_id':run['run_id'],'scenario_id':case['scenario_id'],'reviewer':'','notes':'',
        'language_pass':None,'intent_shape_pass':None,'consistency_pass':None,
        'all_prose_claims_reviewed':None,'prose_claims':[],
        'components':{str(i):{'required_facts_and_behavior_pass':None,'notes':''} for i,_ in enumerate(case['components'] or [None])},
        'actions':{str(i):{'constraint_and_access_pass':None,'notes':''} for i,_ in enumerate(run.get('trace',[]))}}

def write_csv(path,rows):
    if not rows:return
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

METRICS = (
    'e2e_structured', 'cc_structured', 'tool_syntax_validity', 'hcs',
    'schema_validity', 'structured_consistency_pass', 'entity_grounding',
    'structured_ucr', 'tool_error_rate',
    'e2e', 'cc', 'tv', 'ucr', 'seconds', 'cost_usd',
)


def summarize(scores, scenario_ids, repetition_ids):
    groups = {}
    for row in scores:
        groups.setdefault((row['model'], row['system']), []).append(row)
    per_run, summary = [], []
    for (model, system), rows in sorted(groups.items()):
        for metric in METRICS:
            metric_runs = []
            for repetition in repetition_ids:
                batch = [row for row in rows if row['run_id'] == repetition]
                values = [row[metric] for row in batch if row.get(metric) is not None]
                complete = {row['scenario_id'] for row in batch} == scenario_ids
                result = {
                    'model': model, 'system': system, 'metric': metric, 'run_id': repetition,
                    'expected_cases': len(scenario_ids), 'attempted_cases': len(batch),
                    'scored_cases': len(values), 'unscored_attempts': len(batch) - len(values),
                    'complete_run': complete,
                    'score': statistics.mean(values) if values else None,
                }
                per_run.append(result)
                requires_all_scores = metric in {'e2e', 'cc', 'e2e_structured', 'cc_structured', 'schema_validity'}
                if complete and values and (not requires_all_scores or len(values) == len(batch)):
                    metric_runs.append(result['score'])
            all_runs_scored = len(metric_runs) == len(repetition_ids)
            summary.append({
                'model': model, 'system': system, 'metric': metric,
                'runs_scored': len(metric_runs), 'runs_expected': len(repetition_ids),
                'mean': statistics.mean(metric_runs) if all_runs_scored else None,
                'sample_variance': statistics.variance(metric_runs) if all_runs_scored else None,
                'sample_sd': statistics.stdev(metric_runs) if all_runs_scored else None,
            })
    return per_run, summary

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--runs', required=True, nargs='+', help='One or more runs.jsonl files')
    p.add_argument('--project', required=True)
    p.add_argument('--frozen', required=True, help='frozen20.json exported by the notebook')
    p.add_argument('--split',choices=['development','validation','final_test'],default='development')
    p.add_argument('--pricing', default=str(PRICING_DEFAULT),
                   help='Local per-model published rate table; set blank to disable estimates')
    p.add_argument('--allow-final-test',action='store_true');p.add_argument('--reviews');p.add_argument('--out',required=True)
    a=p.parse_args()
    pricing=json.loads(Path(a.pricing).read_text(encoding='utf-8')) if a.pricing else None
    if a.split=='final_test' and not a.allow_final_test:p.error('Final test requires explicit --allow-final-test after freezing settings')
    root=Path(a.project);package=root/'evaluation/scenario_package'
    gold=json.loads((package/a.split/'gold.json').read_text())
    manifest=json.loads((package/'manifest.json').read_text());db=root/'data/final/knowledge_base.sqlite'
    digest=hashlib.sha256(db.read_bytes()).hexdigest()
    if digest!=manifest['snapshot']['sha256']:raise ValueError('Database snapshot mismatch')
    frozen = json.loads(Path(a.frozen).read_text())
    selected = {c['scenario_id']: c for c in frozen['cases']}
    repetitions = frozen['run_ids']
    if len(selected) != 20 or len(frozen['cases']) != 20 or len(repetitions) != 3 or len(set(repetitions)) != 3:
        p.error('Expected the frozen set of 20 unique cases and three distinct run IDs.')
    cases = {c['scenario_id']: c for c in gold if c['scenario_id'] in selected}
    if cases.keys() != selected.keys() or any(
        cases[sid]['prompt'] != c['prompt'] or cases[sid]['language'] != c['language']
        or hashlib.sha256(c['prompt'].encode()).hexdigest() != c['prompt_sha256']
        for sid, c in selected.items()
    ):
        p.error('Frozen cases do not match the selected gold split.')
    runs = []
    keys = set()
    attempt_ids = set()
    for path in a.runs:
        for line in Path(path).read_text().splitlines():
            if not line.strip():
                continue
            raw = json.loads(line)
            attempt_id = raw['attempt_id']
            run_id = raw['run_id']
            key = (raw['model'], raw['system'], raw['scenario_id'], run_id)
            if raw['scenario_id'] not in selected or run_id not in repetitions:
                p.error(f'Attempt outside frozen benchmark: {key}')
            if not isinstance(attempt_id, str) or not attempt_id or attempt_id in attempt_ids or key in keys:
                p.error(f'Duplicate or invalid attempt: {key}')
            attempt_ids.add(attempt_id)
            keys.add(key)
            runs.append(dict(raw, run_id=attempt_id, repetition_id=run_id))
    if not runs:
        p.error('No attempts found.')
    reviews = {r['run_id']:r for r in json.loads(Path(a.reviews).read_text())} if a.reviews else {}
    import sys
    sys.path.insert(0,str(root))
    from src.shared_tools.kb_tools import TOOLS
    tools={t['function']['name']:t['function']['parameters'] for t in TOOLS}
    schema=json.loads((root/'schemas/response.schema.json').read_text())
    conn=sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True);conn.row_factory=sqlite3.Row
    scores=[];review_templates=[];queue=[]
    try:
        for r in runs:
            c=cases.get(r['scenario_id'])
            if c is None:raise ValueError(f"Unknown benchmark ID {r['scenario_id']}; S1-S5 are demo IDs")
            if r.get('request')!=c['prompt']:raise ValueError('Prompt differs from gold: '+c['scenario_id'])
            if r.get('database_sha256')!=digest:raise ValueError('Run DB hash missing or differs')
            rv=reviews.get(r['run_id'])
            if rv and rv.get('scenario_id')!=c['scenario_id']:raise ValueError('Review case mismatch')
            scores.append(evaluate(r,c,schema,conn,tools,rv,manifest['snapshot']['hotel_snapshot_date'],pricing))
            review_templates.append(template(r,c))
            queue.append({'run_id':r['run_id'],'prompt':c['prompt'],'behavior':c['behavior'],
                          'components':c['components'],'response':r.get('response'),'trace':r.get('trace')})
    finally:conn.close()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    for name,value in [('scores.json',scores),('review_template.json',review_templates),('review_queue.json',queue)]:
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2))
    write_csv(out/'scores.csv',[{k:v for k,v in s.items() if not isinstance(v,(dict,list))} for s in scores])
    per_run, summary = summarize(scores, set(selected), repetitions)
    write_csv(out/'run_scores.csv', per_run)
    write_csv(out/'summary.csv', summary)
    print(json.dumps({'runs':len(scores),'review_pending':sum(s['review_pending'] for s in scores),
           'costed_attempts':sum(s['cost_usd'] is not None for s in scores),
          'note':'Use e2e_structured, cc_structured and tool_syntax_validity for the automated score. e2e, cc, tv and ucr require optional prose/intent review.'}))
if __name__=='__main__':main()
