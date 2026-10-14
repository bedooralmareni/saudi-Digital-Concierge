"""Offline checks of submitted notebook code; no GPU, downloads, or API calls."""
import ast
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from src.vector_store.embedder import StubEmbedder

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / 'M4 - Baseline running/notebooks/Saudi_Digital_Concierge_OpenAI_API_Clean.ipynb'
QWEN = ROOT / 'M4 - Baseline running/notebooks/single_model_colab.ipynb'


def cell(path, number):
    notebook = json.loads(path.read_text(encoding='utf-8'))
    return ''.join(notebook['cells'][number - 1]['source'])


@pytest.mark.parametrize('path', [API, QWEN])
def test_notebook_code_compiles_and_outputs_are_currently_clear(path):
    notebook = json.loads(path.read_text(encoding='utf-8'))
    for item in notebook['cells']:
        if item['cell_type'] == 'code':
            ast.parse(''.join(item['source']))
            assert item['outputs'] == []
            assert item['execution_count'] is None


@pytest.fixture
def database(tmp_path):
    path = tmp_path / 'kb.sqlite'
    with sqlite3.connect(path) as conn:
        conn.executescript('''
            CREATE TABLE hotels(hotel_id TEXT, name TEXT, city TEXT, price_sar REAL,
                star_rating REAL, guest_rating REAL, max_persons INT, source TEXT, snapshot_date TEXT);
            INSERT INTO hotels VALUES
                ('h1','Hotel One','Riyadh',200,4,9,2,'fixture','2020-04-24'),
                ('h2','Hotel Two','Riyadh',400,4,8,2,'fixture','2020-04-24'),
                ('h3','Missing rating','Riyadh',100,3,NULL,2,'fixture','2020-04-24'),
                ('h4','Single room','Riyadh',100,3,9,1,'fixture','2020-04-24'),
                ('h5','Other city','Jeddah',150,4,9,2,'fixture','2020-04-24');
            CREATE TABLE events(event_id TEXT, name TEXT, city TEXT, start_date TEXT,
                end_date TEXT, source TEXT, source_url TEXT);
            INSERT INTO events VALUES
                ('e1','Overlapping','Riyadh','2026-10-14','2026-10-15','fixture','https://example.com'),
                ('e2','Single day','Riyadh','2026-10-17',NULL,'fixture','https://example.com'),
                ('e3','Too late','Riyadh','2026-10-18',NULL,'fixture','https://example.com');
        ''')
    return path


class FakeIndex:
    """Tiny NumPy substitute for FAISS's native index."""
    def __init__(self, dim):
        self.dim = dim

    def add(self, values):
        self.values = values

    def search(self, query, k):
        scores = query @ self.values.T
        ids = np.argsort(-scores, axis=1)[:, :k]
        return np.take_along_axis(scores, ids, axis=1), ids


@pytest.fixture
def api_tools(database, monkeypatch):
    monkeypatch.setitem(sys.modules, 'faiss', SimpleNamespace(IndexFlatIP=FakeIndex))
    scope = {'DB_PATH': str(database)}
    exec(cell(API, 8), scope)
    stub = StubEmbedder()
    scope['embedder'] = SimpleNamespace(encode=lambda texts, **kwargs: stub.encode(texts, kind='query'))
    scope['metadata'] = pd.DataFrame([
        {'entity_id': 'p1', 'canonical_id': 'C1', 'city': 'Riyadh', 'entity_type': 'place',
         'category': 'Italian|restaurant', 'text': 'Cafe One — Italian restaurant', 'source': 'fixture', 'source_url': None},
        {'entity_id': 'p2', 'canonical_id': 'C1', 'city': 'Riyadh', 'entity_type': 'place',
         'category': 'Italian|restaurant', 'text': 'Cafe One — restaurant', 'source': 'fixture', 'source_url': None},
        {'entity_id': 'p3', 'canonical_id': None, 'city': 'Jeddah', 'entity_type': 'place',
         'category': 'restaurant', 'text': 'Elsewhere — restaurant', 'source': 'fixture', 'source_url': None},
    ])
    scope['vectors'] = stub.encode(scope['metadata']['text'])
    return scope


def test_api_hotel_constraints_and_native_ratings(api_tools):
    search = api_tools['search_hotels']
    hits = search('الرياض', max_price_per_night=400, min_guest_rating=8, guests=2)
    assert [hit['hotel_id'] for hit in hits] == ['h1', 'h2']
    assert hits[1]['price_sar'] == 400  # Inclusive tool boundary.
    assert hits[0]['snapshot_date'] == '2020-04-24'
    assert search('Riyadh', max_price_per_night=50) == []


def test_api_event_date_overlap_and_invalid_range(api_tools):
    search = api_tools['search_events']
    assert [hit['event_id'] for hit in search('Riyadh', '2026-10-15', '2026-10-17')] == ['e1', 'e2']
    with pytest.raises(ValueError, match='Invalid date range'):
        search('Riyadh', '2026-10-17', '2026-10-15')


def test_api_semantic_search_keeps_ids_city_and_provenance(api_tools):
    search = api_tools['search_places']
    hits = search('Italian restaurant', 'الرياض', 'restaurant')
    assert len(hits) == 1
    assert hits[0]['reference_id'] == 'C1'
    assert hits[0]['city'] == 'Riyadh'
    assert hits[0]['source'] == 'fixture'
    assert hits[0]['source_url'] is None
    assert search('restaurant', 'Abha', 'restaurant') == []


class Message:
    def __init__(self, content=None, calls=None):
        self.content = content
        self.tool_calls = calls

    def model_dump(self, **kwargs):
        return {'role': 'assistant', 'content': self.content, 'tool_calls': [
            {'id': call.id, 'type': 'function', 'function': vars(call.function)} for call in self.tool_calls
        ]}


def agent_scope(messages, result):
    import re
    requests = []
    queue = iter(messages)

    def create(**kwargs):
        requests.append(dict(kwargs, messages=list(kwargs['messages'])))
        next_item = next(queue)
        if isinstance(next_item, Exception):
            raise next_item
        return SimpleNamespace(choices=[SimpleNamespace(message=next_item)])

    scope = {'time': time, 're': re, 'json': json, 'TOOLS': [], 'OPENAI_MODEL': 'fixture-model',
             'execute_tool': lambda name, args: result,
             'client': SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))}
    exec(cell(API, 11), scope)
    return scope, requests


def tool_message():
    call = SimpleNamespace(id='call-1', function=SimpleNamespace(name='search_hotels', arguments='{"city":"Riyadh"}'))
    return Message(calls=[call])


@pytest.mark.parametrize('result,status', [([{'hotel_id': 'h1'}], 'completed'), ([], 'completed'),
                                           ({'error': 'Database unavailable'}, 'retrieval_failed')])
def test_api_agent_retrieves_before_answer_and_distinguishes_errors(result, status):
    scope, requests = agent_scope([tool_message(), Message('Grounded answer')], result)
    answer = scope['run_agent']('Suggest a Riyadh hotel')
    assert answer['status'] == status
    assert answer['trace'][0]['result'] == result
    assert [request['tool_choice'] for request in requests] == ['required', 'auto']
    tool = requests[1]['messages'][-1]
    assert tool['tool_call_id'] == 'call-1'
    assert json.loads(tool['content']) == result


def test_api_rejects_answer_without_retrieval():
    scope, _ = agent_scope([Message('Unsupported answer')], [])
    assert scope['run_agent']('Riyadh hotel')['status'] == 'retrieval_failed'


def test_api_error_preserves_previous_tool_trace():
    scope, _ = agent_scope([tool_message(), RuntimeError('API offline')], [{'hotel_id': 'h1'}])
    answer = scope['run_agent']('Riyadh hotel')
    assert answer['status'] == 'error'
    assert answer['trace'][0]['result'][0]['hotel_id'] == 'h1'


@pytest.mark.parametrize('notebook', [API, QWEN])
def test_missing_kb_rebuilds_in_order_without_network(tmp_path, notebook):
    calls = []
    def run(args, **kwargs):
        calls.append((args, kwargs))
        if args[-1] == 'src.vector_store.build_index':
            store = tmp_path / 'data/final/vector_store'
            store.mkdir(parents=True)
            (tmp_path / 'data/final/knowledge_base.sqlite').touch()
            for name in ['vectors.npy', 'vector_meta.csv', 'index_info.json']:
                (store / name).touch()
    scope = {'ROOT': tmp_path, 'Path': Path, 'sys': sys, 'json': json, 'pd': pd, 'os': os,
             'subprocess': SimpleNamespace(run=run)}
    exec(cell(notebook, 4), scope)
    assert [args[-1] for args, _ in calls] == [
        'src.entity_resolution.resolve', 'src.database.build_sqlite', 'src.vector_store.build_index']
    assert all(kwargs['env']['EMBED_MODEL'] == 'intfloat/multilingual-e5-base' for _, kwargs in calls)


def test_qwen_retrieval_applies_filters_and_excludes_unknown(database):
    scope = {'DB': database}
    exec(cell(QWEN, 5), scope)
    scope['hybrid_search'] = lambda *args, **kwargs: pd.DataFrame([
        {'entity_id': 'h3', 'canonical_id': 'C3'}, {'entity_id': 'h1', 'canonical_id': 'C1'},
        {'entity_id': 'h2', 'canonical_id': 'C2'}, {'entity_id': 'h5', 'canonical_id': 'C5'}])
    hits = scope['retrieve_evidence']('hotel', 'Riyadh', 'hotel', max_price=250, min_rating=8, min_persons=2)
    assert len(hits) == 1
    assert hits[0]['reference_id'] == 'C1'
    assert hits[0]['facts']['price_sar'] == 200
    assert scope['retrieve_evidence']('hotel', 'Riyadh', 'hotel', max_price=50) == []


def test_qwen_demo_displays_saves_and_skips_generation_without_evidence(tmp_path, capsys):
    calls = []
    evidence = [{'reference_id': 'C1', 'facts': {'name': 'Hotel One'}}]
    scope = {'Path': Path, 'json': json, 'MODEL_ID': 'fixture-model', 'SEED': 42, 'GENERATION_OPTIONS': {},
             'retrieve_evidence': lambda *args, **kwargs: evidence, 'TEST_OUTPUT_DIR': tmp_path,
             'generate_answer': lambda *args: calls.append(args) or 'Hotel One [C1]'}
    # Avoid creating /content on the Windows test machine.
    exec(cell(QWEN, 8).replace('Path("/content/baseline_results")', 'TEST_OUTPUT_DIR'), scope)
    scope['run_baseline']('hotel', 'Riyadh', 'hotel')
    assert len(calls) == 1
    saved = json.loads(next(tmp_path.glob('*.json')).read_text(encoding='utf-8'))
    assert saved['evidence'] == evidence and saved['answer'] == 'Hotel One [C1]'
    assert 'KB evidence:' in capsys.readouterr().out
    evidence.clear()
    scope['run_baseline']('hotel', 'Riyadh', 'hotel')
    assert len(calls) == 1
    assert len(list(tmp_path.glob('*.json'))) == 2


def test_api_demo_displays_and_saves_result_without_real_api(tmp_path, capsys):
    record = {'status': 'completed', 'answer': 'Hotel One [h1]', 'trace': [
        {'tool': 'search_hotels', 'result': [{'hotel_id': 'h1', 'price_sar': 200}]}], 'elapsed_seconds': 0.1}
    calls = []
    scope = {'ROOT': tmp_path, 'json': json, 'OPENAI_MODEL': 'fixture-model',
             'run_agent': lambda *args, **kwargs: calls.append(args) or record}
    exec(cell(API, 13), scope)
    assert len(calls) == 1
    saved = json.loads(scope['result_path'].read_text(encoding='utf-8'))
    assert saved['trace'] == record['trace']
    assert saved['model'] == 'fixture-model' and saved['answer'] == 'Hotel One [h1]'
    assert 'KB evidence (tool results):' in capsys.readouterr().out
    exec(cell(API, 14), scope)
    assert len(calls) == 1  # Batch stays disabled by default.
