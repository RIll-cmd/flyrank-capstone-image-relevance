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
    monkeypatch.setattr(module,'embed',lambda text,job_id=None:[1.0,0.0])
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
