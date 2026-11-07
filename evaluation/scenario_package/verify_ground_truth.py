"""Validate the frozen scenario set against its exact source database. Standard library only.
This validates the benchmark, not model responses. Usage: python verify_ground_truth.py /path/knowledge_base.sqlite
"""
import collections, hashlib, json, pathlib, sqlite3, sys

def main():
    root=pathlib.Path(__file__).resolve().parent
    dbpath=pathlib.Path(sys.argv[1]).resolve()
    manifest=json.loads((root/'manifest.json').read_text())
    assert hashlib.sha256(dbpath.read_bytes()).hexdigest()==manifest['snapshot']['sha256'],'Database version mismatch. Rebuild and revalidate gold before using another snapshot.'
    db=sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    allcases=[]
    for slug,split,n,typ,edge,langn in [('development','Development',60,42,18,30),('validation','Validation',20,14,6,10),('final_test','Final Test',20,14,6,10)]:
        cases=json.loads((root/slug/'gold.json').read_text());prompts=[json.loads(s) for s in (root/slug/'prompts.jsonl').read_text().splitlines()]
        assert len(cases)==n
        assert collections.Counter(c['scenario_type'] for c in cases)=={'Typical':typ,'Edge':edge}
        assert collections.Counter(c['language'] for c in cases)=={'AR':langn,'EN':langn}
        assert all(c['split']==split for c in cases)
        unit={'Development':6,'Validation':2,'Final Test':2}[split]
        assert collections.Counter(c['domain'] for c in cases if c['scenario_type']=='Typical')=={'Hotels':2*unit,'Restaurants':unit,'Entertainment':unit,'Events':unit,'Hotel + activity':unit,'Hotel + event':unit}
        assert prompts==[{k:c[k] for k in ['scenario_id','language','prompt']} for c in cases]
        assert {'NO_MATCH','INSUFFICIENT_DATA','CLARIFY','PARTIAL'} <= {c['expected_status'] for c in cases if c['scenario_type']=='Edge'}
        allcases.extend(cases)
    assert len({x['scenario_id'] for x in allcases})==100
    assert len({x['prompt'].strip().casefold() for x in allcases})==100
    groups=collections.defaultdict(set);signatures=collections.defaultdict(list)
    components=0;evidence_rows=0
    for case in allcases:
        groups[case['leakage_group']].add(case['split'])
        sig=[]
        for c in case['components']:
            actual=[dict(r) for r in db.execute(c['sql'],c['params'])]
            assert actual==c['evidence'],(case['scenario_id'],'evidence changed')
            ids=[r[c['id_field']] for r in actual]
            assert ids==c['supporting_ids'] and len(ids)==c['candidate_record_count']
            distinct=collections.defaultdict(list)
            for r in actual:
                key=(r['name'].strip().casefold(),r.get('city'))
                if c['table']=='events':key+=(r['start_date'],r['end_date'])
                distinct[key].append(r[c['id_field']])
            assert len(distinct)==c['distinct_option_count']
            assert list(distinct.values())==c['distinct_option_groups']
            if c['mode']=='recommend':
                assert c['accepted_ids']==ids
                assert len(distinct)>=c['required_count']>0
            else:assert c['accepted_ids']==[]
            if c['mode']=='no_match':assert not actual
            sig.append((c['sql'],c['params'],c['mode'],c['required_count']))
            components+=1;evidence_rows+=len(actual)
        if sig:signatures[json.dumps(sig,sort_keys=True)].append(case['scenario_id'])
    assert all(len(s)==1 for s in groups.values()),'A linked case group crosses splits'
    assert all(len(v)==1 for v in signatures.values()),'Duplicate full task signatures'
    bykey={c['case_key']:c for c in allcases}
    nullfields={'X11':'breakfast_included','X12':'star_rating','X13':'guest_rating','X14':'free_cancellation','X15':'bed_type','X16':'is_family_allowed','X17':'average_rating','X18':'city'}
    for k,field in nullfields.items():assert bykey[k]['components'][0]['evidence'][0][field] is None
    assert db.execute("SELECT count(*) FROM hotels WHERE city='Taif' AND breakfast_included IS NOT NULL").fetchone()[0]==0
    assert db.execute("SELECT count(*) FROM places WHERE city<>'Riyadh'").fetchone()[0]==0
    assert 'opening_hours' not in {r[1] for r in db.execute('PRAGMA table_info(places)')}
    assert not {'price_sar','meal_price','menu_price'} & {r[1] for r in db.execute('PRAGMA table_info(places)')}
    assert bykey['X25']['components'][0]['distinct_option_count']==1
    assert bykey['X25']['components'][0]['candidate_record_count']==2
    event=bykey['X30']['components'][0]['evidence'][0]
    assert event['end_date']<'2026-11-06' and event['is_active']==1
    h=bykey['X20']['components'][0]['evidence'][0]
    assert h['price_sar']==182
    assert db.execute('SELECT snapshot_date FROM hotels WHERE hotel_id=?',[h['hotel_id']]).fetchone()[0]=='2020-04-24'
    # Detect identical component result sets across splits. Shared hotel records are expected;
    # this is a task split over a common KB, not an entity-disjoint benchmark.
    summary={'status':'PASS','cases':len(allcases),'components_reexecuted':components,'evidence_rows_compared':evidence_rows,'split_counts':manifest['counts'],'language_counts':manifest['language_counts'],'database_sha256':manifest['snapshot']['sha256'],'checks':['source fingerprint','exact split/type/language quotas','prompts match gold without answer fields','all SQL results and supporting fields','matching candidates and impossible queries','NULL evidence and absent schema fields','name-city/event-edition distinctness','linked-group isolation','unique prompt text and full query signatures'],'limitations':['No model was run. This is benchmark validation, not response scoring.','No formal semantic paraphrase detector was used. Template and entity overlap are not eliminated.','Operational name-city deduplication may collapse branches with the same name.','Synthetic snapshot-grounded tasks do not establish live booking or itinerary feasibility.']}
    (root/'validation_report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
