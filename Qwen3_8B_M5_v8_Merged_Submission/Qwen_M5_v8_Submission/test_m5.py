"""Offline regression tests. Synthetic responses are TEST FIXTURES, never model results."""
import copy,json,sqlite3,tempfile,unittest,sys
from pathlib import Path
from m5_contract import build_schema,configure_tools,FACT_TYPES,compact_results,parse_tool_calls,VERSION,request_missing_city,request_conflicting_budget,grounding_errors
from m5_evaluate import score_attempt,summarize,evaluate_experiment,REQUIRED
from m5_runner import initialize,digest,file_hash,write_json,run_attempt,reconcile

def run_tests(project,frozen):
    project=Path(project);frozen=json.loads(Path(frozen).read_text()) if not isinstance(frozen,dict) else frozen
    if str(project) not in sys.path:sys.path.insert(0,str(project))
    import src.shared_tools.kb_tools as shared
    db=project/'data/final/knowledge_base.sqlite';tools,metadata=configure_tools(shared,db)
    schema=build_schema(json.loads((project/'schemas/response.schema.json').read_text()))
    gold={x['scenario_id']:x for x in json.loads((project/'evaluation/scenario_package/development/gold.json').read_text())}
    snap=json.loads((project/'evaluation/scenario_package/manifest.json').read_text())['snapshot']
    conn=sqlite3.connect(db);conn.row_factory=sqlite3.Row
    ts={t['function']['name']:t['function']['parameters'] for t in tools}
    from m5_evaluate import record

    def fixture(sid,seed=17):
        case=gold[sid];status={'MATCH':'complete','NO_MATCH':'no_match','COVERAGE_GAP':'coverage_gap','INSUFFICIENT_DATA':'insufficient_data','CLARIFY':'needs_clarification','PARTIAL':'partial'}[case['expected_status']]
        obj={'schema_version':'2.0','scenario_id':sid,'language':case['language'].lower(),
             'response_type':'recommendations','status':status,'message':'TEST FIXTURE ONLY',
             'recommendations':[],'days':[],'constraint_results':[],'clarifying_questions':[],
             'limitations':[],'clarification_target':None,'lookup':None,'issue_codes':[],
             'costs':{'recorded_hotel_price_sar':None,'hotel_price_snapshot_date':None,
                      'verified_trip_total_sar':None,'unknown_cost_categories':[]}}
        trace=[]
        def add(name,args,result):
            trace.append({'call_id':str(len(trace)),'name':name,'arguments':args,'raw_arguments':json.dumps(args),'result':result,'status':'completed'})
        for c in case['components']:
            kind=c['component']
            if c['mode']=='recommend':
                rows=[]
                for group in c['distinct_option_groups'][:c['required_count']]:
                    rid=group[0];row=record(conn,kind,rid);rows.append(dict(row,record_id=rid,entity_type=kind))
                    item={'entity_type':kind,'record_id':rid,'name':row['name'],'city':row['city'],
                          'recorded_hotel_price_sar':row['price_sar'] if kind=='hotel' else None,
                          'hotel_price_snapshot_date':snap['hotel_snapshot_date'] if kind=='hotel' else None,
                          'event_start_date':row['start_date'] if kind=='event' else None,
                          'event_end_date':row['end_date'] if kind=='event' else None,'reason':'TEST FIXTURE ONLY',
                          'facts':{k:row.get(k) for k in FACT_TYPES}}
                    obj['recommendations'].append(item)
                name={'hotel':'search_hotels','event':'search_events','activity':'search_places','restaurant':'search_places'}[kind]
                args={'city':rows[0]['city']}
                if kind in ('activity','restaurant'):args['entity_type']='entertainment' if kind=='activity' else 'restaurant';args['semantic']=False
                add(name,args,compact_results(rows))
                if kind=='hotel':obj['issue_codes'].append('historical_hotel_price')
                if kind=='event':obj['issue_codes'].append('historical_event_dates')
            elif c['mode']=='no_match':
                if kind=='hotel':args={'city':'Abha','max_price_sar':30,'guests':2};name='search_hotels';code='no_match'
                else:args={'city':'Jeddah','entity_type':'restaurant','semantic':False};name='search_places';code='restaurant_coverage_gap'
                add(name,args,[]);obj['issue_codes'].append(code)
            elif c['mode']=='unknown':
                rid=c['supporting_ids'][0];row=record(conn,kind,rid)
                add('search_hotels',{'record_id':rid},compact_results([dict(row,record_id=rid,entity_type=kind)]))
                obj.update(response_type='information',lookup={'record_id':rid,'field':'breakfast_included','value':None},issue_codes=['unknown_field'])
        if case['expected_status']=='CLARIFY':
            target='city' if sid=='SDC-055' else 'budget'
            obj.update(response_type='clarification',clarification_target=target,
                       clarifying_questions=['Which city?' if target=='city' else 'Which budget?'],
                       issue_codes=['missing_city' if target=='city' else 'conflicting_budget'])
        obj['issue_codes']=list(dict.fromkeys(obj['issue_codes']))
        return {'attempt_id':f'test-{seed}-{sid}','run_id':seed,'scenario_id':sid,'status':'completed','request':case['prompt'],
            'response':obj,'trace':trace,'model_calls':[],'elapsed_seconds':1.0,'generation_seconds':0.5,
            'usage_totals':{'total_tokens':100},'elapsed_seconds_is_partial':False}
    def score(r,review=None):return score_attempt(r,gold[r['scenario_id']],schema,conn,ts,snap['hotel_snapshot_date'],review)

    class Checks(unittest.TestCase):
        def test_all_twenty_gold_fixtures(self):
            self.assertEqual(set(REQUIRED),{x['scenario_id'] for x in frozen['cases']})
            for c in frozen['cases']:
                s=score(fixture(c['scenario_id']));self.assertEqual(s['e2e_structured'],1,(c['scenario_id'],s))
        def test_requested_facts_cannot_be_omitted(self):
            for k in ['max_persons','guest_rating']:
                r=fixture('SDC-007');r['response']['recommendations'][0]['facts'][k]=None
                self.assertEqual(score(r)['e2e_structured'],0)
            r=fixture('SDC-007');r['response']['recommendations'][0]['recorded_hotel_price_sar']=None
            self.assertEqual(score(r)['e2e_structured'],0)
        def test_fabricated_fact_fails(self):
            r=fixture('SDC-007');r['response']['recommendations'][0]['facts']['max_persons']=999
            self.assertGreater(score(r)['structured_unsupported_rate'],0)
            self.assertEqual(score(r)['e2e_structured'],0)
        def test_duplicate_options_fail(self):
            r=fixture('SDC-007');r['response']['recommendations'][1]=copy.deepcopy(r['response']['recommendations'][0])
            self.assertEqual(score(r)['e2e_structured'],0)
        def test_wrong_city_no_match_fails(self):
            r=fixture('SDC-043');r['trace'][0]['arguments']['city']='Jeddah'
            r['trace'][0]['raw_arguments']=json.dumps(r['trace'][0]['arguments'])
            self.assertEqual(score(r)['e2e_structured'],0)
        def test_extra_no_match_filter_fails(self):
            r=fixture('SDC-043');r['trace'][0]['arguments']['min_stars']=5
            self.assertEqual(score(r)['e2e_structured'],0)
        def test_unknown_is_not_false(self):
            r=fixture('SDC-048');r['response']['lookup']['value']=False
            self.assertEqual(score(r)['e2e_structured'],0)
        def test_coverage_gap_is_distinct(self):
            r=fixture('SDC-045');r['response']['status']='no_match'
            self.assertEqual(score(r)['e2e_structured'],0)
        def test_contradictory_issue_code_fails(self):
            r=fixture('SDC-007');r['response']['issue_codes'].append('conflicting_budget')
            self.assertEqual(score(r)['e2e_structured'],0)
        def test_city_preflight_generalizes_and_respects_direct_lookup(self):
            self.assertTrue(request_missing_city('Recommend accommodation for two people with recorded price at most SAR 300.',metadata))
            self.assertTrue(request_missing_city('رشح لي فندق لشخصين بحد أقصى 300 ريال',metadata))
            self.assertFalse(request_missing_city('رشح لي فندقين في الرياض',metadata))
            self.assertFalse(request_missing_city('Recommend hotels in Jeddah',metadata))
            self.assertFalse(request_missing_city('For Corp Inn Deira (hotels_00007), is breakfast included?',metadata))
        def test_public_taxonomy_covers_db_without_gold(self):
            self.assertIn('Saudi', metadata['restaurant_category_tags'])
            self.assertIn('Amusement center', metadata['entertainment_genres'])
            self.assertEqual(metadata['restaurant_table_cities'],['Riyadh'])
        def test_price_conflict_preflight_is_conservative(self):
            self.assertTrue(request_conflicting_budget('أريد فندقًا في جدة سعره أقل من 200 ريال وفي الوقت نفسه أكثر من 500 ريال'))
            self.assertTrue(request_conflicting_budget('Find a hotel under 200 and simultaneously above 500 SAR'))
            self.assertFalse(request_conflicting_budget('أريد فندقين، أحدهما أقل من 200 والآخر أكثر من 500 ريال'))
            self.assertFalse(request_conflicting_budget('Hotel for two people, at most SAR 300'))
        def test_searched_empty_results_do_not_become_clarification(self):
            r=fixture('SDC-043')
            r['response']['response_type']='clarification'
            r['response']['status']='needs_clarification'
            self.assertTrue(any('zero matches' in v for v in grounding_errors(r['response'],r['trace'],r['request'],metadata)))
        def test_preflight_budget_prevents_any_tools(self):
            case=next(c for c in frozen['cases'] if c['scenario_id']=='SDC-056')
            cfg={'model':'TEST-STUB','database_sha256':file_hash(db),'schema':schema,'tools':tools,
                 'system_prompt':'Test','shared_context':{'AR':'ctx','EN':'ctx'},'public_metadata':metadata,
                 'snapshot':snap,'max_retrieval_rounds':8,'max_tool_calls':8,
                 'preflight_budget_gate':True,'grounding_audit':False,'final_instruction':'JSON'}
            stages=[]
            def gen(messages,phase,cfg):
                stages.append(phase)
                return {'text':json.dumps(fixture('SDC-056')['response']),'finish_reason':'stop',
                  'elapsed_seconds':0.1,'usage':{'prompt_tokens':10,'completion_tokens':10,'total_tokens':20}}
            with tempfile.TemporaryDirectory() as temp:
                folder,manifest=initialize(temp,'budget_test',cfg,frozen)
                got=run_attempt(case,17,folder,manifest,None,gen,seed_fn=lambda _:None)
            self.assertEqual(stages,['final'])
            self.assertEqual(got['retrieval_transition'],'preflight_conflicting_budget')
            self.assertEqual(got['trace'],[])
        def test_grounding_audit_detects_cross_domain_rating(self):
            r=fixture('SDC-001');o=r['response'];o['recommendations'][0]['facts']['guest_rating']=4.3
            self.assertTrue(any('guest_rating' in v for v in grounding_errors(o,r['trace'])))
        def test_grounding_audit_detects_missing_event_code(self):
            r=fixture('SDC-038');r['response']['issue_codes']=[]
            self.assertTrue(any('historical_event_dates' in v for v in grounding_errors(r['response'],r['trace'])))
        def test_grounding_audit_direct_lookup_does_not_claim_room_price(self):
            r=fixture('SDC-048');r['response']['costs']['recorded_hotel_price_sar']=312
            self.assertTrue(any('no selected hotel' in v for v in grounding_errors(r['response'],r['trace'])))
        def test_missing_city_tool_call_must_not_count_as_success(self):
            r=fixture('SDC-055')
            r['trace'].append({'call_id':'oops','name':'search_hotels','arguments':{'guests':2},
                 'raw_arguments':'{"guests": 2}', 'result':{'error':'city required'},'status':'error'})
            self.assertEqual(score(r)['e2e_structured'],0)
            self.assertEqual(score(r)['component_completion'],0)
        def test_missing_city_requires_clarification(self):
            r=fixture('SDC-055');r['response']['clarification_target']=None
            self.assertEqual(score(r)['e2e_structured'],0)
        def test_valid_undated_itinerary_is_accepted(self):
            r=fixture('SDC-020');o=r['response'];o['days']=[{'day_number':1,'date':None,'items':o['recommendations']}]
            o['recommendations']=[];o['response_type']='itinerary'
            self.assertEqual(score(r)['e2e_structured'],1)
            o['days'][0]['date']='2030-01-01';self.assertEqual(score(r)['e2e_structured'],0)
        def test_failed_attempt_not_rewarded(self):
            r=fixture('SDC-007');r['status']='incomplete_final'
            self.assertEqual(score(r)['e2e_structured'],0);self.assertEqual(score(r)['component_completion'],0)
        def test_no_retrieval_is_not_grounded(self):
            r=fixture('SDC-007');r['trace']=[];self.assertEqual(score(r)['e2e_structured'],0)
        def test_no_calls_is_not_100_percent_tool_validity(self):
            self.assertIsNone(score(fixture('SDC-055'))['tool_syntax_validity'])
        def test_missing_review_not_a_zero_score(self):
            self.assertIsNone(score(fixture('SDC-007'))['e2e_reviewed'])
        def test_prose_claims_require_review(self):
            r=fixture('SDC-007');r['response']['message']='A fabricated booking guarantee.'
            self.assertIsNone(score(r)['e2e_reviewed'])
            review={'reviewer':'test','evidence_notes':'Contradicts historical snapshot.','language_pass':True,
                    'required_text_and_behavior_pass':True,'all_text_claims_supported':False,'intent_and_consistency_pass':True}
            self.assertEqual(score(r,review)['e2e_reviewed'],0)
        def test_call_parser_does_not_drop_malformed_suffix(self):
            calls=parse_tool_calls('<tool_call>{"name":"search_hotels","arguments":{"city":"Riyadh"}}</tool_call><tool_call>{')
            self.assertEqual(len(calls),2);self.assertIn('parse_error',calls[1])
            self.assertIn('parse_error',parse_tool_calls('<tool_call>{"name":"a","name":"b","arguments":{}}</tool_call>')[0])
        def test_payload_cap_and_nonfinite_arguments(self):
            self.assertEqual(len(compact_results([{'record_id':str(i)} for i in range(10)])),5)
            self.assertIn('parse_error',parse_tool_calls('<tool_call>{"name":"search_hotels","arguments":{"max_price_sar":NaN}}</tool_call>')[0])
        def test_city_aliases_and_payload(self):
            kb=shared.KnowledgeBaseTools(db)
            self.assertEqual(kb.search_hotels(city='Khobar'),kb.search_hotels(city='Al Khobar'))
            self.assertEqual(kb.search_hotels(city='Medina'),kb.search_hotels(city='Madinah'))
            self.assertEqual(metadata['restaurant_table_cities'],['Riyadh'])
            self.assertNotIn('description',compact_results([{'record_id':'x','description':'long'}])[0])
        def test_partial_batch_has_no_publishable_mean(self):
            scores=[score(fixture(c['scenario_id'],seed)) for seed in [17,29,43] for c in frozen['cases']]
            _,s=summarize(scores,frozen['cases'],[17,29,43]);self.assertEqual(next(x for x in s if x['metric']=='e2e_structured')['mean'],1)
            _,s=summarize(scores[:-1],frozen['cases'],[17,29,43]);self.assertIsNone(next(x for x in s if x['metric']=='e2e_structured')['mean'])
        def test_runner_and_manifest(self):
            case=next(c for c in frozen['cases'] if c['scenario_id']=='SDC-007');r=fixture('SDC-007')
            cfg={'model':'TEST-STUB','database_sha256':file_hash(db),'schema':schema,'tools':tools,
                 'system_prompt':'Test only','shared_context':{'AR':'context','EN':'context'},'public_metadata':metadata,
                 'snapshot':snap,'max_retrieval_rounds':8,'max_tool_calls':8,'grounding_audit':False,'final_instruction':'Return JSON'}
            replies=iter([{'text':'<tool_call>{"name":"search_hotels","arguments":{"city":"Riyadh","max_price_sar":300,"guests":2,"min_guest_rating":8}}</tool_call>','finish_reason':'stop'},
                          {'text':'Ready','finish_reason':'stop'}, {'text':json.dumps(r['response']),'finish_reason':'stop'}])
            def gen(*args):return dict(next(replies),elapsed_seconds=0.1,usage={'prompt_tokens':10,'completion_tokens':10,'total_tokens':20})
            seeds=[]
            with tempfile.TemporaryDirectory() as temp:
                folder,manifest=initialize(temp,'fixture',cfg,frozen)
                run=run_attempt(case,17,folder,manifest,shared.KnowledgeBaseTools(db),gen,seed_fn=seeds.append)
                self.assertEqual(seeds,[17]);self.assertEqual(run['status'],'completed');self.assertEqual(len(run['trace']),1)
                self.assertEqual(run['usage_totals']['total_tokens'],60)
                with self.assertRaises(FileExistsError):run_attempt(case,17,folder,manifest,None,None)
                with self.assertRaises(RuntimeError):initialize(temp,'fixture',dict(cfg,model='different'),frozen)
                p=folder/'attempts'/'17_SDC-007.json';run['status']='started';write_json(p,run);reconcile(folder)
                self.assertEqual(json.loads(p.read_text())['status'],'interrupted')
        def run_sequence(self, sequence, max_rounds=8, max_calls=8, max_final_repairs=0, scenario_id='SDC-007', grounding_audit=False):
            case=next(c for c in frozen['cases'] if c['scenario_id']==scenario_id)
            cfg={'model':'TEST-STUB','database_sha256':file_hash(db),'schema':schema,'tools':tools,
                 'system_prompt':'Test only','shared_context':{'AR':'context','EN':'context'},'public_metadata':metadata,
                 'snapshot':snap,'max_retrieval_rounds':max_rounds,'max_tool_calls':max_calls,'max_final_repairs':max_final_repairs,'grounding_audit':grounding_audit,'final_instruction':'Return JSON'}
            phases=[];replies=iter(sequence)
            def gen(messages,phase,cfg):
                phases.append(phase)
                if phase=='retrieval':self.assertNotIn('Final JSON schema:',messages[0]['content'])
                if phase=='final':self.assertTrue(any('Final JSON schema:' in m['content'] for m in messages if m['role']=='user'))
                text,finish=next(replies)
                return {'text':text,'finish_reason':finish,'elapsed_seconds':0.1,
                        'usage':{'prompt_tokens':10,'completion_tokens':10,'total_tokens':20}}
            with tempfile.TemporaryDirectory() as temp:
                folder,manifest=initialize(temp,'runner_fixture',cfg,frozen)
                run=run_attempt(case,17,folder,manifest,shared.KnowledgeBaseTools(db),gen,seed_fn=lambda _:None)
            return run,phases
        def test_ready_marker_goes_to_final(self):
            r,p=self.run_sequence([('<ready/>','stop'),(json.dumps(fixture('SDC-007')['response']),'stop')])
            self.assertEqual(p,['retrieval','final']);self.assertEqual(r['retrieval_transition'],'ready_marker')
            self.assertEqual(r['status'],'completed')
        def test_truncated_answer_draft_goes_to_final(self):
            draft='{"message":"TRUNCATED_DRAFT_SENTINEL'
            r,p=self.run_sequence([(draft,'length'),(json.dumps(fixture('SDC-007')['response']),'stop')])
            self.assertEqual(r['status'],'completed');self.assertEqual(p,['retrieval','final'])
            self.assertEqual(r['retrieval_transition'],'answer_draft_discarded')
            self.assertIn(draft,r['model_calls'][0]['text'])
            self.assertFalse(any('TRUNCATED_DRAFT_SENTINEL' in m['content'] for m in r['messages']))
        def test_truncated_tool_is_not_executed(self):
            bad='<tool_call>{"name":"search_hotels","arguments":{'
            r,p=self.run_sequence([(bad,'length'),('<ready/>','stop'),(json.dumps(fixture('SDC-007')['response']),'stop')])
            self.assertEqual(r['status'],'completed');self.assertEqual(r['trace'][0]['status'],'not_executed')
            self.assertEqual(p,['retrieval','retrieval','final'])
        def test_truncated_prose_consumes_bounded_rounds(self):
            r,p=self.run_sequence([('unfinished reasoning','length'),(json.dumps(fixture('SDC-007')['response']),'stop')],max_rounds=1)
            self.assertTrue(r['tool_budget_exhausted']);self.assertEqual(p,['retrieval','final'])
        def test_retrieval_timeout_stays_failure(self):
            r,p=self.run_sequence([('{"message":"cut','timeout')])
            self.assertEqual(r['status'],'timeout');self.assertEqual(p,['retrieval'])
        def test_final_truncation_is_not_repaired(self):
            r,p=self.run_sequence([('<ready/>','stop'),('{"message":"cut','length')])
            self.assertEqual(r['status'],'incomplete_final');self.assertIsNone(r['response'])
        def test_duplicate_json_repair_is_logged_and_not_silent(self):
            valid=json.dumps(fixture('SDC-007')['response'])
            r,phases=self.run_sequence([('<ready/>','stop'),('{"x":1,"x":2}','stop'),(valid,'stop')],max_final_repairs=1)
            self.assertEqual(r['status'],'completed')
            self.assertEqual(phases,['retrieval','final','final'])
            self.assertEqual(r['final_repairs_used'],1)
            self.assertEqual(len(r['final_drafts']),2)
            self.assertEqual(r['final_drafts'][0]['status'],'invalid_json')
            self.assertEqual(r['final_drafts'][1]['status'],'completed')
            self.assertEqual(len([x for x in r['model_calls'] if x['phase']=='final']),2)
        def test_schema_repair_requires_new_model_output(self):
            invalid=fixture('SDC-007')['response'];invalid.pop('days')
            valid=json.dumps(fixture('SDC-007')['response'])
            r,phases=self.run_sequence([('<ready/>','stop'),(json.dumps(invalid),'stop'),(valid,'stop')],max_final_repairs=1)
            self.assertEqual(r['status'],'completed')
            self.assertEqual(r['final_drafts'][0]['status'],'schema_invalid')
            self.assertEqual(r['final_drafts'][1]['status'],'completed')
        def test_grounding_audit_triggers_logged_model_repair(self):
            item=fixture('SDC-001')['response']
            broken=copy.deepcopy(item)
            broken['recommendations'][0]['facts']['guest_rating']=4.3
            call='<tool_call>{"name":"search_places","arguments":{"city":"Al Khobar","genre":"Science museum","entity_type":"entertainment","min_rating":3.5,"top_k":1}}</tool_call>'
            run,phases=self.run_sequence([(call,'stop'),('<ready/>','stop'),
                     (json.dumps(broken),'stop'),(json.dumps(item),'stop')],
                     max_final_repairs=1,scenario_id='SDC-001',grounding_audit=True)
            self.assertEqual(run['status'],'completed')
            self.assertEqual(run['final_repairs_used'],1)
            self.assertEqual(run['final_drafts'][0]['status'],'grounding_inconsistent')
            self.assertEqual(run['final_drafts'][1]['status'],'completed')
            self.assertEqual(phases,['retrieval','retrieval','final','final'])
            self.assertTrue(any('guest_rating' in e for e in run['final_drafts'][0]['validation_errors']))
        def test_repair_failure_remains_failure(self):
            r,phases=self.run_sequence([('<ready/>','stop'),('not json','stop'),('still not json','stop')],max_final_repairs=1)
            self.assertEqual(r['status'],'invalid_json')
            self.assertEqual(r['final_repairs_used'],1)
            self.assertEqual(len(r['final_drafts']),2)
            self.assertIsNone(r['response'])
        def test_invalid_second_draft_does_not_reuse_first_response(self):
            invalid=fixture('SDC-007')['response'];invalid.pop('days')
            r,p=self.run_sequence([('<ready/>','stop'),(json.dumps(invalid),'stop'),('still invalid JSON','stop')],max_final_repairs=1)
            self.assertEqual(r['status'],'invalid_json')
            self.assertIsNone(r['response'])
            self.assertEqual(r['final_drafts'][0]['status'],'schema_invalid')
        def test_duplicate_final_keys_are_rejected(self):
            r,p=self.run_sequence([('<ready/>','stop'),('{"x":1,"x":2}','stop')])
            self.assertEqual(r['status'],'invalid_json')
        def test_missing_final_field_is_not_filled(self):
            obj=fixture('SDC-007')['response'];obj.pop('days')
            r,p=self.run_sequence([('<ready/>','stop'),(json.dumps(obj),'stop')])
            self.assertEqual(r['status'],'schema_invalid');self.assertNotIn('days',r['response'])
        def test_invalid_argument_feedback_then_valid_call(self):
            bad='<tool_call>{"name":"search_hotels","arguments":{"max_guests":2}}</tool_call>'
            good='<tool_call>{"name":"search_hotels","arguments":{"city":"Riyadh","guests":2,"limit":1}}</tool_call>'
            r,p=self.run_sequence([(bad,'stop'),(good,'stop'),('<ready/>','stop'),(json.dumps(fixture('SDC-007')['response']),'stop')])
            self.assertEqual([t['status'] for t in r['trace']],['error','completed'])
            self.assertEqual(r['trace'][0]['result']['error_type'],'InvalidArguments')
        def test_tool_budget_limits_execution(self):
            call='<tool_call>{"name":"search_hotels","arguments":{"city":"Riyadh","limit":1}}</tool_call>'
            r,p=self.run_sequence([(call*3,'stop'),(json.dumps(fixture('SDC-007')['response']),'stop')],max_calls=2)
            self.assertEqual(sum(t['status']=='completed' for t in r['trace']),2)
            self.assertTrue(r['tool_budget_exhausted'])
        def test_smoke_is_not_m5_submission(self):
            smoke=copy.deepcopy(frozen);smoke['cases']=smoke['cases'][:5]
            cfg={'contract_version':VERSION,'benchmark_sha256':digest(smoke),'source_hashes':{},
                 'module_hashes':{},'database_sha256':file_hash(db),'schema':schema,'tools':tools,
                 'snapshot':snap,'seeds':[17,29,43],'run_mode':'smoke5'}
            with tempfile.TemporaryDirectory() as temp:
                folder,manifest=initialize(temp,'smoke',cfg,smoke)
                self.assertEqual(manifest['planned_attempts'],15)
                for seed in smoke['run_ids']:
                    for c in smoke['cases']:
                        r=fixture(c['scenario_id'],seed)
                        r.update(config_sha256=manifest['config_sha256'],database_sha256=cfg['database_sha256'])
                        write_json(folder/'attempts'/f"{seed}_{c['scenario_id']}.json",r)
                ready,_=evaluate_experiment(project,folder)
                self.assertEqual(ready['expected_attempts'],15)
                self.assertTrue(ready['all_attempts_recorded']);self.assertTrue(ready['diagnostic_report_ready'])
                self.assertFalse(ready['automatic_report_ready']);self.assertFalse(ready['m5_minimum_case_count_met'])
                self.assertIn('15/15',(folder/'m5_results/M5_REPORT.md').read_text())
        def test_full_export_and_review_resume(self):
            cfg={'contract_version':VERSION,'benchmark_sha256':digest(frozen),'source_hashes':{},
                 'module_hashes':{},'database_sha256':file_hash(db),'schema':schema,'tools':tools,
                 'snapshot':snap,'seeds':[17,29,43]}
            with tempfile.TemporaryDirectory() as temp:
                folder,manifest=initialize(temp,'evaluation_fixture',cfg,frozen)
                records=[fixture(c['scenario_id'],seed) for seed in [17,29,43] for c in frozen['cases']]
                for r in records:
                    r.update(config_sha256=manifest['config_sha256'],database_sha256=cfg['database_sha256'])
                for r in records[:3]:write_json(folder/'attempts'/f"{r['run_id']}_{r['scenario_id']}.json",r)
                ready,_=evaluate_experiment(project,folder)
                self.assertFalse(ready['automatic_report_ready'])
                for r in records[3:]:write_json(folder/'attempts'/f"{r['run_id']}_{r['scenario_id']}.json",r)
                ready,summary=evaluate_experiment(project,folder,folder/'human_review.json')
                self.assertTrue(ready['automatic_report_ready']);self.assertFalse(ready['full_prose_review_ready'])
                self.assertEqual(len(json.loads((folder/'human_review.json').read_text())),60)
                self.assertEqual(next(s for s in summary if s['metric']=='e2e_structured')['mean'],1)
                self.assertTrue((folder/'m5_results/M5_REPORT.md').exists())
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    conn.close()
    if not result.wasSuccessful():raise AssertionError('M5 regression suite failed')
    return {'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'scope':'Offline fixtures only; no Qwen generations or benchmark results.'}

if __name__=='__main__':
    print(json.dumps(run_tests(sys.argv[1],sys.argv[2]),indent=2))
