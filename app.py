import json
import os
import threading
import time
import uuid
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import BackgroundTasks, FastAPI, HTTPException
from dotenv import load_dotenv
from guard import assess, cosine, infer_subject
from models import ImageIn, PostIn, ReviewIn
from provider import embed, vision
from ranking import composition_bonus
from store import connect, initialize

load_dotenv()

@asynccontextmanager
async def lifespan(app):
    initialize()
    with connect() as db:
        db.execute("UPDATE jobs SET status='interrupted' WHERE status IN ('queued','running')")
    yield

app = FastAPI(title='Image understanding and matching', lifespan=lifespan)
job_lock = threading.Lock()

@app.get('/health')
def health(): return {'status': 'ok'}

@app.post('/images', status_code=201)
def add_image(item: ImageIn):
    root = Path(os.getenv('IMAGE_DIR', 'images')).resolve()
    path = (root / item.path).resolve()
    if not path.is_relative_to(root) or not path.is_file(): raise HTTPException(400, 'Image must be an existing file under IMAGE_DIR')
    if path.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp'): raise HTTPException(400, 'Unsupported image type')
    with connect() as db:
        cursor = db.execute('INSERT INTO images(path,source,license) VALUES(?,?,?)', (str(path),item.source,item.license))
        return {'id':cursor.lastrowid, 'status':'pending'}

@app.get('/images')
def images():
    with connect() as db: return [dict(x) for x in db.execute('SELECT id,path,source,license,metadata,status,error FROM images ORDER BY id')]

def process(job_id, ids):
    with job_lock:
        with connect() as db: db.execute("UPDATE jobs SET status='running' WHERE id=?", (job_id,))
        for image_id in ids:
            with connect() as db: row = db.execute('SELECT * FROM images WHERE id=?', (image_id,)).fetchone()
            error = None
            for attempt in range(3):
                try:
                    meta = vision(row['path'],job_id)
                    vector = embed(meta['caption']+'; '+meta['subject']+'; '+', '.join(meta['attributes']),job_id)
                    state = 'flagged' if meta['confidence'] < 0.75 else 'ready'
                    with connect() as db:
                        db.execute('UPDATE images SET metadata=?,embedding=?,status=?,error=NULL WHERE id=?', (json.dumps(meta),json.dumps(vector),state,image_id))
                        db.execute('DELETE FROM image_tags WHERE image_id=?', (image_id,))
                        tags=set([meta['subject'],meta['category'],*meta['attributes']])
                        db.executemany('INSERT INTO image_tags(image_id,tag) VALUES(?,?)',[(image_id,t) for t in tags])
                    error = None
                    break
                except Exception as exc:
                    error = str(exc)[:300]
                    if attempt < 2: time.sleep(2**attempt)
            with connect() as db:
                if error:
                    db.execute("UPDATE images SET status='failed',error=? WHERE id=?", (error,image_id))
                    db.execute('UPDATE jobs SET failed=failed+1 WHERE id=?', (job_id,))
                db.execute('UPDATE jobs SET completed=completed+1 WHERE id=?', (job_id,))
        with connect() as db: db.execute("UPDATE jobs SET status='done' WHERE id=?", (job_id,))

@app.post('/jobs', status_code=202)
def create_job(background: BackgroundTasks):
    with connect() as db:
        ids = [x['id'] for x in db.execute("SELECT id FROM images WHERE status IN ('pending','failed')")]
        if not ids: raise HTTPException(400,'No pending or failed images')
        job_id = str(uuid.uuid4())
        db.execute('INSERT INTO jobs(id,status,total) VALUES(?,?,?)', (job_id,'queued',len(ids)))
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
    query = item.title+'\n'+item.content
    if expected != 'unknown' and expected.lower() not in query.lower(): query += '\nCanonical subject: '+expected
    try: vector = embed(query, kind='query')
    except Exception as exc: raise HTTPException(503,'Embedding provider unavailable') from exc
    with connect() as db:
        cursor=db.execute('INSERT INTO posts(title,content,expected_subject,embedding) VALUES(?,?,?,?)',(item.title,item.content,expected,json.dumps(vector)))
        return {'id':cursor.lastrowid}

def ranking(post_id):
    with connect() as db:
        post=db.execute('SELECT * FROM posts WHERE id=?',(post_id,)).fetchone()
        if not post: raise HTTPException(404,'Post not found')
        rows=db.execute("SELECT * FROM images WHERE metadata IS NOT NULL AND embedding IS NOT NULL").fetchall()
    candidates=[]
    for row in rows:
        meta=json.loads(row['metadata']); similarity=cosine(json.loads(post['embedding']),json.loads(row['embedding']))
        result=assess(post['expected_subject'],meta,similarity,float(os.getenv('SIMILARITY_THRESHOLD','0.72')),float(os.getenv('CONFIDENCE_THRESHOLD','0.75')))
        bonus=composition_bonus(post['title']+' '+post['content'],meta['caption'])
        candidates.append({'image_id':row['id'],'metadata':meta,'similarity':round(similarity,4),'rank_score':round(similarity+bonus,4),**result})
    with connect() as db:
        db.executemany('''INSERT INTO suggestions(post_id,image_id,similarity,accepted,reason) VALUES(?,?,?,?,?)
            ON CONFLICT(post_id,image_id) DO UPDATE SET similarity=excluded.similarity,accepted=excluded.accepted,reason=excluded.reason,updated_at=CURRENT_TIMESTAMP''',
            [(post_id,c['image_id'],c['similarity'],int(c['accepted']),c['reason']) for c in candidates])
    return sorted(candidates,key=lambda c:c['rank_score'],reverse=True)

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
        cursor=db.execute('INSERT INTO reviews(post_id,image_id,decision,note) VALUES(?,?,?,?)',(post_id,image_id,item.decision,item.note))
        return {'id':cursor.lastrowid,'decision':item.decision}

@app.get('/reviews')
def reviews():
    with connect() as db: return [dict(x) for x in db.execute('SELECT * FROM reviews ORDER BY id DESC')]
