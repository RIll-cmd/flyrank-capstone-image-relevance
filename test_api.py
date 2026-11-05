import json
from fastapi.testclient import TestClient
import app as module

def test_batch_match_reject_and_review(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'data.db'))
    monkeypatch.setenv('IMAGE_DIR',str(tmp_path))
    (tmp_path/'fox.jpg').write_bytes(b'fake')
    (tmp_path/'wolf.jpg').write_bytes(b'fake')
    def vision(path,job):
        return {'subject':'red fox' if 'fox' in path else 'gray wolf','category':'animal','attributes':[],'caption':'an animal','confidence':0.95}
    monkeypatch.setattr(module,'vision',vision)
    monkeypatch.setattr(module,'embed',lambda text,job_id=None,kind='document':[1.0,0.0])
    with TestClient(module.app) as c:
        fox=c.post('/images',json={'path':'fox.jpg','source':'source','license':'test'}).json()['id']
        wolf=c.post('/images',json={'path':'wolf.jpg','source':'source','license':'test'}).json()['id']
        job=c.post('/jobs').json()['id']
        assert c.get('/jobs/'+job).json()['completed']==2
        post=c.post('/posts',json={'title':'Foxes','content':'Red fox behavior','expected_subject':'red fox'}).json()['id']
        results=c.get(f'/posts/{post}/images').json()
        assert results['suggestions'][0]['image_id']==fox
        assert results['rejected'][0]['image_id']==wolf
        assert 'mismatch' in results['rejected'][0]['reason']
        assert c.post(f'/posts/{post}/images/{wolf}/reviews',json={'decision':'approve'}).status_code==400
        assert c.post(f'/posts/{post}/images/{fox}/reviews',json={'decision':'approve'}).status_code==201
        unmatched=c.post('/posts',json={'title':'An unfamiliar animal','content':'An otter in a river','expected_subject':'otter'}).json()['id']
        response=c.get(f'/posts/{unmatched}/images').json()
        assert response['status']=='no confident match' and response['reason']

def test_latin_alias_adds_canonical_subject_to_embedding(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'data.db'))
    calls=[]
    def embed(text,job_id=None,kind='document'):
        calls.append((text,kind)); return [1.0,0.0]
    monkeypatch.setattr(module,'embed',embed)
    with TestClient(module.app) as c:
        result=c.post('/posts',json={'title':'Vulpes vulpes','content':'A woodland species.'})
        assert result.status_code==201
    assert calls[0][1]=='query' and 'Canonical subject: red fox' in calls[0][0]
