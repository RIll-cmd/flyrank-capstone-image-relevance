import pytest
from fastapi.testclient import TestClient
import app
from guard import assess
from store import initialize,reserve_call

def test_category_contradiction_is_rejected():
    assert not assess('red fox',{'subject':'red fox','category':'plant','confidence':.99},.99)['accepted']

def test_model_call_budget_is_atomic_and_bounded(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'budget.db'));monkeypatch.setenv('MAX_MODEL_CALLS_PER_DAY','1')
    initialize();reserve_call()
    with pytest.raises(RuntimeError,match='budget'):reserve_call()

def test_tenant_keys_isolate_records(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'tenants.db'));monkeypatch.setenv('TENANT_API_KEYS','{"alpha-key":"alpha","beta-key":"beta"}')
    monkeypatch.setattr(app,'embed',lambda *a,**kw:[1.,0.])
    with TestClient(app.app) as c:
        assert c.get('/images').status_code==401
        post=c.post('/posts',headers={'X-API-Key':'alpha-key'},json={'title':'Fox','content':'A red fox.'}).json()['id']
        assert c.get(f'/posts/{post}/images',headers={'X-API-Key':'beta-key'}).status_code==404

def test_retried_image_and_post_registration_are_idempotent(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'db.sqlite'));monkeypatch.setenv('IMAGE_DIR',str(tmp_path))
    (tmp_path/'one.jpg').write_bytes(b'test');calls=[]
    monkeypatch.setattr(app,'embed',lambda *a,**kw:calls.append(1) or [1.,0.])
    with TestClient(app.app) as c:
        image={'path':'one.jpg','source':'test','license':'test'}
        assert c.post('/images',json=image).json()['id']==c.post('/images',json=image).json()['id']
        post={'title':'A fox','content':'A red fox'}
        assert c.post('/posts',json=post).json()['id']==c.post('/posts',json=post).json()['id']
    assert len(calls)==1

def test_failed_batch_creates_failure_alert(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'db.sqlite'));monkeypatch.setenv('IMAGE_DIR',str(tmp_path))
    (tmp_path/'one.jpg').write_bytes(b'test')
    def fail(*a):raise RuntimeError('test provider failure')
    monkeypatch.setattr(app,'vision',fail);monkeypatch.setattr(app.time,'sleep',lambda seconds:None)
    with TestClient(app.app) as c:
        c.post('/images',json={'path':'one.jpg','source':'test','license':'test'})
        job=c.post('/jobs').json()['id']
        assert c.get('/jobs/'+job).json()['failed']==1
        assert c.get('/alerts').json()[0]['job_id']==job

def test_overlapping_batch_submission_cannot_claim_same_image(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'db.sqlite'));monkeypatch.setenv('IMAGE_DIR',str(tmp_path))
    (tmp_path/'one.jpg').write_bytes(b'test');calls=[]
    monkeypatch.setattr(app,'process',lambda job,ids:calls.append(ids))
    with TestClient(app.app) as c:
        c.post('/images',json={'path':'one.jpg','source':'test','license':'test'})
        assert c.post('/jobs').status_code==202
        assert c.post('/jobs').status_code==400
    assert len(calls)==1
