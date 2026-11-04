import os, tempfile
os.environ['APPLYPILOT_DB']=tempfile.mktemp(suffix='.db')
from fastapi.testclient import TestClient
from app import app
client=TestClient(app)
def test_matching_and_approval():
 j={'company':'Demo','title':'AI Engineer','url':'https://example.org/job1','description':'Python FastAPI LLM agents and SQL'}
 r=client.post('/jobs/evaluate',json=j); assert r.status_code==200
 assert r.json()['decision']=='review'
 id=r.json()['id']; assert client.post(f'/applications/{id}/review',json={'approved':True}).json()['sent'] is False

def test_spanish_block():
 j={'company':'Demo','title':'AI Engineer','url':'https://example.org/job2','description':'Python; advanced Spanish required'}
 assert client.post('/jobs/evaluate',json=j).json()['decision']=='reject'
