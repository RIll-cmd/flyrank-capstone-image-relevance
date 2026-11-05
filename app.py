import json
import os
import threading
import time
import uuid
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import BackgroundTasks, FastAPI, HTTPException,Security
from fastapi.security import APIKeyHeader
from dotenv import load_dotenv
from guard import assess, cosine, infer_subject
from models import ImageIn, PostIn, ReviewIn
from provider import embed, vision
from ranking import composition_bonus
import services
import match_service
from store import connect, initialize,alert
from tenancy import TenantMiddleware

load_dotenv()

@asynccontextmanager
async def lifespan(app):
    initialize()
    with connect() as db:
        db.execute("UPDATE jobs SET status='interrupted' WHERE status IN ('queued','running')")
        db.execute("UPDATE images SET status='pending' WHERE status='processing'")
    yield

app = FastAPI(title='Image understanding and matching', lifespan=lifespan,dependencies=[Security(APIKeyHeader(name='X-API-Key',auto_error=False))])
app.add_middleware(TenantMiddleware)

@app.get('/health')
def health(): return {'status': 'ok'}

@app.post('/images', status_code=201)
def add_image(item: ImageIn):
    root = Path(os.getenv('IMAGE_DIR', 'images')).resolve()
    path = (root / item.path).resolve()
    if not path.is_relative_to(root) or not path.is_file(): raise HTTPException(400, 'Image must be an existing file under IMAGE_DIR')
    if path.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp'): raise HTTPException(400, 'Unsupported image type')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        existing=db.execute('SELECT id,status FROM images WHERE path=?',(str(path),)).fetchone()
        if existing:return dict(existing)
        cursor = db.execute('INSERT INTO images(path,source,license) VALUES(?,?,?)', (str(path),item.source,item.license))
        return {'id':cursor.lastrowid, 'status':'pending'}

@app.get('/images')
def images():
    with connect() as db: return [dict(x) for x in db.execute('SELECT id,path,source,license,metadata,status,error FROM images ORDER BY id')]

def process(job_id,ids):
    return services.process(job_id,ids,vision,embed,time.sleep)

@app.post('/jobs', status_code=202)
def create_job(background: BackgroundTasks):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        ids = [x['id'] for x in db.execute("SELECT id FROM images WHERE status IN ('pending','failed')")]
        if not ids: raise HTTPException(400,'No pending or failed images')
        job_id = str(uuid.uuid4())
        db.execute('INSERT INTO jobs(id,status,total) VALUES(?,?,?)', (job_id,'queued',len(ids)))
        db.executemany("UPDATE images SET status='processing' WHERE id=?",[(i,) for i in ids])
    background.add_task(process,job_id,ids)
    return {'id':job_id,'status':'queued','total':len(ids)}

@app.get('/jobs/{job_id}')
def get_job(job_id: str):
    with connect() as db:
        row = db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        if not row: raise HTTPException(404,'Job not found')
        calls = [dict(x) for x in db.execute('SELECT * FROM model_calls WHERE job_id=?',(job_id,))]
    return {**dict(row),'calls':calls}

@app.post('/posts', status_code=201)
def add_post(item: PostIn):
    expected = item.expected_subject.strip() or infer_subject(item.title+' '+item.content) or 'unknown'
    with connect() as db:
        existing=db.execute('SELECT id FROM posts WHERE title=? AND content=? AND expected_subject=?',(item.title,item.content,expected)).fetchone()
        if existing:return {'id':existing['id']}
    query = item.title+'\n'+item.content
    if expected != 'unknown' and expected.lower() not in query.lower(): query += '\nCanonical subject: '+expected
    try: vector = embed(query, kind='query')
    except Exception as exc: raise HTTPException(503,'Embedding provider unavailable') from exc
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        existing=db.execute('SELECT id FROM posts WHERE title=? AND content=? AND expected_subject=?',(item.title,item.content,expected)).fetchone()
        if existing:return {'id':existing['id']}
        cursor=db.execute('INSERT INTO posts(title,content,expected_subject,embedding) VALUES(?,?,?,?)',(item.title,item.content,expected,json.dumps(vector)))
        return {'id':cursor.lastrowid}

def ranking(post_id):
    try:return match_service.ranking(post_id)
    except LookupError as exc:raise HTTPException(404,str(exc)) from exc

@app.get('/posts/{post_id}/images')
def suggest(post_id: int):
    results=ranking(post_id); accepted=[r for r in results if r['accepted']]
    reason=None if accepted else ('No processed images are available' if not results else 'All candidates failed the mismatch guard; see rejection reasons')
    return {'status':'suggestions' if accepted else 'no confident match','reason':reason,'suggestions':accepted,'rejected':[r for r in results if not r['accepted']]}

@app.get('/posts/{post_id}/images/{image_id}')
def inspect_candidate(post_id: int,image_id: int):
    return next((r for r in ranking(post_id) if r['image_id']==image_id),None) or (_ for _ in ()).throw(HTTPException(404,'Processed image not found'))

@app.post('/posts/{post_id}/images/{image_id}/reviews',status_code=201)
def review(post_id: int,image_id: int,item: ReviewIn):
    if item.decision not in ('approve','reject'): raise HTTPException(400,'Decision must be approve or reject')
    candidate=inspect_candidate(post_id,image_id)
    if item.decision=='approve' and not candidate['accepted']: raise HTTPException(400,'Cannot approve a candidate rejected by the guard')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        existing=db.execute('SELECT id FROM reviews WHERE post_id=? AND image_id=? AND decision=? AND note=?',(post_id,image_id,item.decision,item.note)).fetchone()
        if existing:return {'id':existing['id'],'decision':item.decision}
        cursor=db.execute('INSERT INTO reviews(post_id,image_id,decision,note) VALUES(?,?,?,?)',(post_id,image_id,item.decision,item.note))
        return {'id':cursor.lastrowid,'decision':item.decision}

@app.get('/reviews')
def reviews():
    with connect() as db: return [dict(x) for x in db.execute('SELECT * FROM reviews ORDER BY id DESC')]

@app.get('/alerts')
def alerts():
    with connect() as db:return [dict(x) for x in db.execute('SELECT * FROM alerts ORDER BY id DESC')]
