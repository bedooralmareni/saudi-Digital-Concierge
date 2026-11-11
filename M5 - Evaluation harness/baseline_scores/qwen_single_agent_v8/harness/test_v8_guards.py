"""Additional fixture-only tests for v8 changes. No model generation or gold used."""
import json, tempfile, unittest
from pathlib import Path
from m5_contract import explicit_request_city, request_component_hints, grounding_errors
from m5_runner import run_attempt

class V8Guards(unittest.TestCase):
    def test_explicit_cities_and_abstention(self):
        self.assertEqual(explicit_request_city('أريد متحفًا في المدينة المنورة'), 'Madinah')
        self.assertEqual(explicit_request_city('Find a hotel in Al Khobar'), 'Al Khobar')
        self.assertIsNone(explicit_request_city('Find a hotel in Riyadh and Jeddah'))
        self.assertIsNone(explicit_request_city('Find a hotel near my office'))

    def test_component_hints_with_bilingual_counts(self):
        self.assertEqual(request_component_hints('فندق لشخصين ومطعمان في جدة'),
                         ({'hotel':1,'restaurant':2},{'hotel':1,'restaurant':2}))
        k,c=request_component_hints('One accommodation option and one event in Riyadh')
        self.assertEqual((k.get('hotel'),k.get('event'),c.get('hotel')), (1,1,1))
        k,c=request_component_hints('list 2 distinct events in Riyadh')
        self.assertEqual(k.get('event'),2)

    def test_status_repair_without_gold(self):
        r={'record_id':'hotels_demo','entity_type':'hotel','name':'Hotel Demo','city':'Riyadh','price_sar':200,'snapshot_date':'2021-01-01'}
        e={'record_id':'events_demo','entity_type':'event','name':'Festival Demo','city':'Riyadh','start_date':'2023-01-01','end_date':'2023-01-02'}
        h={'record_id':r['record_id'],'entity_type':'hotel','name':r['name'],'city':r['city'],
           'recorded_hotel_price_sar':200,'hotel_price_snapshot_date':'2021-01-01','facts':{}}
        ev={'record_id':e['record_id'],'entity_type':'event','name':e['name'],'city':e['city'],
           'event_start_date':'2023-01-01','event_end_date':'2023-01-02','facts':{}}
        trace=[{'status':'completed','result':[r,e]}]
        o={'response_type':'recommendations','status':'partial','recommendations':[h,ev],
           'issue_codes':['historical_hotel_price','historical_event_dates'],'costs':{}}
        errors=grounding_errors(o,trace,'One accommodation option and one event in Riyadh',{})
        self.assertTrue(any('status MUST be complete' in s for s in errors),errors)

    def test_coverage_gap_repair_without_gold(self):
        o={'response_type':'recommendations','status':'partial','recommendations':[],
           'issue_codes':['no_match'],'costs':{}}
        errors=grounding_errors(o,[{'status':'completed','result':[]}],
                               'Recommend three restaurants in Jeddah',
                               {'restaurant_table_cities':['Riyadh']})
        self.assertTrue(any('status MUST be coverage_gap' in s for s in errors), errors)

    def test_model_calls_dedup_and_correct_public_city(self):
        tool={'type':'function','function':{'name':'search_places','description':'Search locations','parameters':{
            'type':'object','additionalProperties':False,'properties':{
                'city':{'type':'string'},'entity_type':{'type':'string'},'top_k':{'type':'integer'}},
            'required':['city','entity_type']}}}
        cfg={'system':'fixture','model':'local','database_sha256':'test','system_prompt':'Test only',
             'shared_context':{'AR':'','EN':''},'public_metadata':{},'snapshot':{},'tools':[tool],
             'schema':{'type':'object','properties':{'scenario_id':{'type':'string'},'language':{'type':'string'}},
                       'required':['scenario_id','language'],'additionalProperties':False},
             'max_tool_calls':8,'max_retrieval_rounds':8,'max_final_repairs':0,
             'preflight_city_gate':False,'preflight_budget_gate':False,'grounding_audit':False,
             'anchor_request_city':True,'normalize_tool_args':True,'dedupe_retrieval':True,
             'final_instruction':'One JSON object.'}
        call='<tool_call>{"name":"search_places","arguments":{"city":"Makkah","entity_type":"entertainment","limit":1}}</tool_call>'
        texts=iter([call,call,'{"scenario_id":"SYN-A","language":"ar"}'])
        class Kb:
            seen=[]
            def execute_tool(self,name,args):
                self.seen.append(dict(args))
                return [{'entity_type':'activity','record_id':'activity_demo','name':'Demo','city':'Madinah'}]
        kb=Kb()
        def generate(messages,phase,cfg):
            return {'text':next(texts),'finish_reason':'stop','usage':{'prompt_tokens':2,'completion_tokens':2,'total_tokens':4},'elapsed_seconds':0.01}
        with tempfile.TemporaryDirectory() as temp:
            out=run_attempt({'scenario_id':'SYN-A','language':'AR','scenario_type':'Typical',
                 'domain':'Entertainment','prompt':'أريد مكان ترفيه في المدينة المنورة'},17,
                 Path(temp),{'config':cfg,'config_sha256':'abc'},kb,generate,seed_fn=lambda _:None)
            self.assertEqual(out['status'],'completed')
            self.assertEqual(out['retrieval_transition'],'duplicate_search_blocked')
            self.assertEqual(len(out['trace']),1)
            self.assertEqual(kb.seen[0]['city'],'Madinah')
            self.assertEqual(kb.seen[0]['top_k'],1)
            self.assertNotIn('limit',kb.seen[0])
            self.assertTrue(any('city_anchored' in q for q in out['protocol_warnings']))

if __name__=='__main__':unittest.main(verbosity=2)
