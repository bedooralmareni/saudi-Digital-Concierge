"""Resumable, single-agent local Qwen runner. Never imports or reads evaluation gold."""
import json,os,re,time,uuid,random,hashlib,copy
from pathlib import Path
from datetime import datetime,timezone
from jsonschema import Draft202012Validator
from m5_contract import parse_tool_calls,compact_results,request_missing_city,request_conflicting_budget,grounding_errors,explicit_request_city,canonical_city

def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def file_hash(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def write_json(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.tmp')
    with tmp.open('w',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
def error_text(e):return re.sub(r'(?i)(hf_[A-Za-z0-9]+|sk-[A-Za-z0-9_-]+|Bearer\s+\S+)','[REDACTED]',str(e))[:1800]

def initialize(root,name,config,benchmark):
    if not re.fullmatch(r'[A-Za-z0-9_-]+',name):raise ValueError('Use a simple experiment name')
    folder=Path(root)/name;folder.mkdir(parents=True,exist_ok=True);p=folder/'experiment_manifest.json'
    manifest={'created_at':now(),'config_sha256':digest(config),'config':config,'planned_attempts':len(benchmark['cases'])*len(benchmark['run_ids'])}
    if p.exists():
        previous=json.loads(p.read_text())
        if previous['config']!=config or previous['config_sha256']!=manifest['config_sha256']:raise RuntimeError('Settings/environment changed. Restore exact versions or use a new experiment name; do not mix attempts.')
        if json.loads((folder/'frozen20.json').read_text())!=benchmark:raise RuntimeError('Benchmark changed')
        manifest=previous
    else:
        if list((folder/'attempts').glob('*.json')):raise RuntimeError('Attempt files without manifest')
        write_json(folder/'frozen20.json',benchmark);write_json(p,manifest)
    for name in ['attempts','events']:(folder/name).mkdir(exist_ok=True)
    return folder,manifest

def seed_all(seed):
    import numpy as np,torch
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    if torch.cuda.is_available():torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark=False
    torch.backends.cudnn.deterministic=True
    if hasattr(torch.backends.cuda.matmul,'allow_tf32'):torch.backends.cuda.matmul.allow_tf32=False
    # Unsupported quantized kernels may not be deterministic. Record warnings, do not claim cross-GPU bitwise equivalence.
    torch.use_deterministic_algorithms(True,warn_only=True)

def generate_qwen(model,tokenizer,messages,phase,cfg):
    import torch
    g=cfg['generation'];kwargs={'tokenize':False,'add_generation_prompt':True,'enable_thinking':False}
    if phase=='retrieval':kwargs['tools']=cfg['tools']
    text=tokenizer.apply_chat_template(messages,**kwargs)
    inputs=tokenizer(text,return_tensors='pt',add_special_tokens=False)
    count=int(inputs['input_ids'].shape[-1]);budget=g['tool_max_new_tokens'] if phase=='retrieval' else g['final_max_new_tokens']
    if count>g['max_input_tokens']:raise RuntimeError(f'ContextLimitExceeded: {count} > {g["max_input_tokens"]}; no content was truncated')
    inputs={k:v.to(model.device) for k,v in inputs.items()}
    torch.cuda.synchronize();started=time.perf_counter()
    phase_temperature=g['tool_temperature'] if phase=='retrieval' else g['final_temperature']
    with torch.inference_mode():
        output=model.generate(**inputs,max_new_tokens=budget,do_sample=True,
            temperature=phase_temperature,top_p=g['top_p'],top_k=g['top_k'],
            repetition_penalty=1.0,min_p=0.0,max_time=g['max_call_seconds'],
            pad_token_id=tokenizer.eos_token_id,use_cache=True)
    torch.cuda.synchronize();seconds=time.perf_counter()-started
    token_ids=output[0,count:].detach().cpu().tolist()
    eos=model.generation_config.eos_token_id
    terminal=set(eos if isinstance(eos,list) else [eos]);terminal.add(tokenizer.eos_token_id)
    ended=bool(token_ids and token_ids[-1] in terminal)
    decode_ids=token_ids[:-1] if ended else token_ids
    raw=tokenizer.decode(decode_ids,skip_special_tokens=False).strip()
    reason='stop' if ended else 'timeout' if seconds>=g['max_call_seconds'] else 'length'
    return {'text':raw,'finish_reason':reason,'elapsed_seconds':seconds,
            'usage':{'prompt_tokens':count,'completion_tokens':len(token_ids),'total_tokens':count+len(token_ids)}}

def totals(run):
    calls=run['model_calls'];complete=all(isinstance(c.get('usage'),dict) for c in calls)
    known={k:sum((c.get('usage') or {}).get(k,0) for c in calls) for k in ['prompt_tokens','completion_tokens','total_tokens']}
    run['known_usage_totals']=known;run['usage_complete']=complete
    run['usage_totals']=known if complete else {k:None for k in known}
    run['known_generation_seconds']=sum(c.get('elapsed_seconds',0) for c in calls)
    run['generation_seconds']=run['known_generation_seconds'] if complete else None
    run['cost_usd']=None

def run_attempt(case,seed,folder,manifest,kb,generate,seed_fn=seed_all):
    cfg=manifest['config'];key=f"{seed}_{case['scenario_id']}";path=folder/'attempts'/f'{key}.json'
    if path.exists():raise FileExistsError(key)
    t0=time.perf_counter();run={'attempt_id':str(uuid.uuid4()),'attempt_key':key,'run_id':seed,'seed':seed,
        'scenario_id':case['scenario_id'],'request':case['prompt'],'language':case['language'],
        'scenario_type':case['scenario_type'],'domain':case['domain'],'model':cfg['model'],
        'system':cfg.get('system','qwen_single_agent_v8'),'config_sha256':manifest['config_sha256'],
        'database_sha256':cfg['database_sha256'],'started_at':now(),'ended_at':None,
        'status':'started','model_calls':[],'trace':[],'messages':[],'response':None,'raw_answer':None,
        'validation_errors':[],'grounding_validation_errors':[],'final_drafts':[],'final_repairs_used':0,'error':None,'tool_budget_exhausted':False,'events_count':0,
        'elapsed_seconds_is_partial':False,'retrieval_transition':None,'protocol_warnings':[]}
    def checkpoint():
        run['elapsed_seconds']=time.perf_counter()-t0;totals(run);write_json(path,run)
    def event(name,payload):
        run['events_count']+=1
        write_json(folder/'events'/key/f"{run['events_count']:04d}_{name}.json",{'at':now(),'event':name,'payload':copy.deepcopy(payload)})
        checkpoint()
    def call(phase):
        entry={'call_index':len(run['model_calls'])+1,'phase':phase,'status':'started','usage':None,'started_at':now()}
        run['model_calls'].append(entry);event('generation_start',entry)
        try:
            result=generate(run['messages'],phase,cfg);entry.update(result,status='returned',ended_at=now());return result
        except BaseException as exc:
            entry.update(status='error',error_type=type(exc).__name__,error=error_text(exc),ended_at=now());raise
        finally:event('generation_end',entry)
    checkpoint()
    try:
        seed_fn(seed)
        system=cfg['system_prompt']+'\n'+cfg['shared_context'][case['language']]+ '\nPublic database metadata:\n'+canonical(cfg['public_metadata'])+'\nSnapshot:\n'+canonical(cfg['snapshot'])
        run['messages']=[{'role':'system','content':system},{'role':'user','content':json.dumps({'scenario_id':case['scenario_id'],'raw_request':case['prompt']},ensure_ascii=False)}]
        event('attempt_start',{'seed':seed,'scenario_id':case['scenario_id']})
        validators={t['function']['name']:Draft202012Validator(t['function']['parameters']) for t in cfg['tools']}
        budget_gate=bool(cfg.get('preflight_budget_gate',False) and
            request_conflicting_budget(case['prompt']))
        city_gate=bool(not budget_gate and cfg.get('preflight_city_gate',False) and
            request_missing_city(case['prompt'],cfg.get('public_metadata',{})))
        if budget_gate:
            run['retrieval_transition']='preflight_conflicting_budget'
            event('retrieval_preflight',{'decision':'conflicting_budget','tool_calls':0})
        if city_gate:
            run['retrieval_transition']='preflight_missing_city'
            event('retrieval_preflight',{'decision':'city_missing','tool_calls':0})
        request_city=explicit_request_city(case['prompt'],cfg.get('public_metadata',{})) if cfg.get('anchor_request_city',False) else None
        seen_queries=set()
        stop_duplicate=False
        for step in range(0 if city_gate or budget_gate else cfg['max_retrieval_rounds']):
            gen=call('retrieval');text=gen['text'];calls=parse_tool_calls(text)
            # Never execute a truncated tool call. An answer-shaped draft is discarded,
            # logged, and regenerated once in the final phase with its full budget.
            if gen['finish_reason']=='timeout':
                run.update(status='timeout',raw_answer=text);return run
            if not calls:
                answer_like=text.lstrip().startswith(('{','```'))
                if gen['finish_reason']!='stop' and not answer_like:
                    run['protocol_warnings'].append('retrieval_length_without_action')
                    event('retrieval_protocol_error',{'step':step+1,'reason':'length_without_action'})
                    run['messages'].append({'role':'user','content':'Your previous output was truncated and discarded. Emit a short tool_call only, or exactly <ready/>. Do not write the answer yet.'})
                    continue
                run['retrieval_transition']='ready_marker' if text.strip()=='<ready/>' else 'answer_draft_discarded' if answer_like else 'no_tool_fallback'
                if run['retrieval_transition']!='ready_marker':run['protocol_warnings'].append(run['retrieval_transition'])
                event('retrieval_to_final',{'step':step+1,'reason':run['retrieval_transition'],'draft_discarded':True})
                break
            if gen['finish_reason']!='stop':
                for j,c in enumerate(calls):
                    run['trace'].append({**c,'call_id':f'{step+1}-{j+1}','step':step+1,'status':'not_executed','result':{'error_type':'IncompleteGeneration','error':'Truncated tool generation was not executed'}})
                run['protocol_warnings'].append('incomplete_tool_generation')
                event('retrieval_protocol_error',{'step':step+1,'reason':'incomplete_tool_generation'})
                if len(run['trace'])>=cfg['max_tool_calls']:
                    run['tool_budget_exhausted']=True;break
                run['messages'].append({'role':'user','content':'Your tool action was truncated and not executed. Return a shorter complete tool_call, or exactly <ready/>. No final answer yet.'})
                continue
            run['messages'].append({'role':'assistant','content':text})
            for j,c in enumerate(calls):
                c=copy.deepcopy(c)
                if isinstance(c.get('arguments'),dict) and c.get('name') in validators:
                    args=c['arguments']
                    if cfg.get('normalize_tool_args',False) and c['name']=='search_places' and 'limit' in args and 'top_k' not in args:
                        args['top_k']=args.pop('limit')
                        run['protocol_warnings'].append('tool_arg_alias:search_places.limit->top_k')
                    if request_city and 'city' in args and isinstance(args['city'],str) and canonical_city(args['city'])!=request_city:
                        before=args['city'];args['city']=request_city
                        run['protocol_warnings'].append(f'city_anchored_from_request:{before}->{request_city}')
                signature=canonical({'name':c.get('name'),'arguments':c.get('arguments')})
                if cfg.get('dedupe_retrieval',False) and signature in seen_queries:
                    run['retrieval_transition']='duplicate_search_blocked'
                    run['protocol_warnings'].append('duplicate_search_blocked')
                    event('duplicate_tool_blocked',{'step':step+1,'name':c.get('name'),'arguments':c.get('arguments')})
                    stop_duplicate=True
                    break
                seen_queries.add(signature)
                entry={**c,'call_id':f'{step+1}-{j+1}','step':step+1,'status':'started','result':None}
                run['trace'].append(entry);event('tool_start',entry);ts=time.perf_counter()
                if len(run['trace'])>cfg['max_tool_calls']:
                    result={'error_type':'ToolBudgetExceeded','error':'Tool call budget exhausted'}
                elif c.get('parse_error'):
                    result={'error_type':'InvalidArguments','error':c['parse_error']}
                elif c['name'] not in validators:
                    result={'error_type':'UnknownTool','error':'Tool name not in the public contract'}
                else:
                    errs=[e.message for e in validators[c['name']].iter_errors(c['arguments'])]
                    result={'error_type':'InvalidArguments','error':'; '.join(errs)} if errs else compact_results(kb.execute_tool(c['name'],c['arguments']))
                entry.update(result=result,status='completed' if isinstance(result,list) else 'error',elapsed_seconds=time.perf_counter()-ts)
                run['messages'].append({'role':'tool','content':canonical(result)})
                event('tool_end',entry)
            if stop_duplicate:break
            if len(run['trace'])>=cfg['max_tool_calls']:
                run['tool_budget_exhausted']=True;break
        else:
            if not city_gate and not budget_gate:run['tool_budget_exhausted']=True
        if run['retrieval_transition'] is None:run['retrieval_transition']='budget_exhausted'
        run['messages'].append({'role':'user','content':cfg['final_instruction']+'\nFinal JSON schema:\n'+canonical(cfg['schema'])})
        # A single, explicitly logged self-correction is permitted using only the
        # public JSON schema and parser errors. Never show gold/evaluator criteria.
        def unique(pairs):
            obj={}
            for k,v in pairs:
                if k in obj:raise ValueError('Duplicate JSON key: '+k)
                obj[k]=v
            return obj
        max_repairs=cfg.get('max_final_repairs',0)
        for final_index in range(max_repairs+1):
            # Each draft stands alone: an invalid second JSON must not leave the
            # first invalid draft in the final response field.
            run['response']=None
            gen=call('final');raw=gen['text'];run['raw_answer']=raw
            run['messages'].append({'role':'assistant','content':raw})
            errors=[];obj=None
            if gen['finish_reason']!='stop':
                run['status']='timeout' if gen['finish_reason']=='timeout' else 'incomplete_final'
                errors=['Final model output did not finish: '+gen['finish_reason']]
            else:
                try:
                    obj=json.loads(raw,object_pairs_hook=unique,
                                   parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON value')))
                except (ValueError,TypeError) as exc:
                    run['status']='invalid_json';errors=[str(exc)]
                else:
                    run['response']=obj
                    errors=[f"{'/'.join(map(str,e.absolute_path))}: {e.message}" for e in
                            Draft202012Validator(cfg['schema']).iter_errors(obj)]
                    if not errors and (obj['scenario_id']!=case['scenario_id'] or
                                       obj['language']!=case['language'].lower()):
                        errors.append('Identity/language mismatch: use scenario_id='+case['scenario_id']+
                                      ', language='+case['language'].lower())
                    grounding=[] if errors or not cfg.get('grounding_audit',True) else grounding_errors(obj,run['trace'],case['prompt'],cfg.get('public_metadata',{}))
                    run['grounding_validation_errors']=grounding
                    if grounding:errors=['Grounding: '+v for v in grounding]
                    run['status']='schema_invalid' if errors and not grounding else 'grounding_inconsistent' if grounding else 'completed' 
            run['validation_errors']=errors
            run['final_drafts'].append({'step':final_index+1,'status':run['status'],
                                        'finish_reason':gen['finish_reason'],
                                        'validation_errors':list(errors),'raw_answer':raw})
            run['final_repairs_used']=final_index
            event('final_validation',{'step':final_index+1,'status':run['status'],'errors':errors[:6]})
            if not errors:break
            if final_index==max_repairs:break
            # Don't attempt to repair a timed-out or context-truncated generation.
            if gen['finish_reason']!='stop':break
            guidance='\n'.join(errors[:6])[:1200]
            run['messages'].append({'role':'user','content':
                'Your previous JSON failed the PUBLIC JSON schema or grounded field audit. Errors: '+guidance+
                '\nRegenerate the ENTIRE JSON from scratch; only one object; no repeated keys, '
                'no extra fields, no markdown. Keep the same request and already retrieved '
                'evidence; no tools, no invented information. Correct scenario_id and language. '
                'The full schema appeared in my preceding instruction. Pay particular attention to exact source names and status.'})
            event('final_repair_requested',{'after_step':final_index+1,'errors':errors[:6]})
    except KeyboardInterrupt:
        run.update(status='interrupted',error={'type':'KeyboardInterrupt','message':'Stopped by user'},elapsed_seconds_is_partial=True);raise
    except Exception as exc:
        message=error_text(exc);kind='oom' if 'out of memory' in message.lower() else 'context_limit' if 'ContextLimitExceeded' in message else 'execution_error'
        run.update(status=kind,error={'type':type(exc).__name__,'message':message})
    finally:
        run['ended_at']=now();event('attempt_end',{'status':run['status']})
    return run

def reconcile(folder):
    for p in (folder/'attempts').glob('*.json'):
        r=json.loads(p.read_text())
        if r['status']=='started':
            r.update(status='interrupted',elapsed_seconds_is_partial=True,interruption_detected_at=now(),
                     error={'type':'RuntimeDisconnected','message':'Interrupted attempt retained; not silently retried'})
            totals(r);write_json(p,r)

def export_runs(folder):
    records=[json.loads(p.read_text()) for p in sorted((folder/'attempts').glob('*.json'))]
    target=folder/'runs.jsonl';tmp=target.with_suffix('.jsonl.tmp')
    with tmp.open('w',encoding='utf-8') as f:
        for row in records:f.write(canonical(row)+'\n')
        f.flush();os.fsync(f.fileno())
    os.replace(tmp,target);return records

def run_benchmark(folder,project,kb,generate,expected_config_hash,selected_scenario_ids=None):
    folder=Path(folder);project=Path(project)
    if selected_scenario_ids is not None:
        selected_scenario_ids=set(selected_scenario_ids)
        if not selected_scenario_ids:
            raise ValueError('No selected scenarios for this batch')
    # Exclusive creation prevents accidental simultaneous writers. A stale lock
    # after a lost runtime requires the explicit recovery cell, never automatic removal.
    lock=folder/'RUNNING.lock'
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:raise RuntimeError('RUNNING.lock exists. Confirm the other runtime is stopped, then use the recovery cell.')
    os.write(fd,f'pid={os.getpid()} started={now()}'.encode());os.close(fd)
    try:
        manifest=json.loads((folder/'experiment_manifest.json').read_text());cfg=manifest['config']
        if digest(cfg)!=manifest['config_sha256'] or digest(cfg)!=expected_config_hash:raise RuntimeError('Config mismatch')
        frozen=json.loads((folder/'frozen20.json').read_text())
        if digest(frozen)!=cfg['benchmark_sha256']:raise RuntimeError('Benchmark mismatch')
        for p,h in cfg['source_hashes'].items():
            if file_hash(project/p)!=h:raise RuntimeError('Source changed: '+p)
        for p,h in cfg['module_hashes'].items():
            if file_hash(Path(__file__).parent/p)!=h:raise RuntimeError('Runner code changed: '+p)
        reconcile(folder)
        if selected_scenario_ids is not None:
            available={c['scenario_id'] for c in frozen['cases']}
            if not selected_scenario_ids<=available:
                raise ValueError('Selected IDs not in frozen benchmark: '+str(sorted(selected_scenario_ids-available)))
        for seed in frozen['run_ids']:
            for case in frozen['cases']:
                if selected_scenario_ids is not None and case['scenario_id'] not in selected_scenario_ids:
                    continue
                key=f"{seed}_{case['scenario_id']}";path=folder/'attempts'/f'{key}.json'
                if path.exists():
                    old=json.loads(path.read_text())
                    if old['config_sha256']!=manifest['config_sha256']:raise RuntimeError('Mixed attempt settings')
                    print(key,'saved:',old['status'],flush=True);continue
                print(key,'running...',flush=True)
                result=run_attempt(case,seed,folder,manifest,kb,generate)
                export_runs(folder);print(key,result['status'],round(result['elapsed_seconds'],1),'s',flush=True)
                if result['status'] in ('oom','execution_error','context_limit'):
                    print('Batch paused after infrastructure error. Preserve this result; inspect the saved error before resuming.',flush=True)
                    return export_runs(folder)
        return export_runs(folder)
    finally:
        export_runs(folder);lock.unlink(missing_ok=True)
