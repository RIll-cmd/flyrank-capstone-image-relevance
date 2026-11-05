import json
import threading
from store import connect,alert

job_lock=threading.Lock()

def process(job_id, ids, vision, embed, sleep):
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
                    if attempt < 2: sleep(2**attempt)
            with connect() as db:
                if error:
                    alert(job_id,image_id,error)
                    db.execute("UPDATE images SET status='failed',error=? WHERE id=?", (error,image_id))
                    db.execute('UPDATE jobs SET failed=failed+1 WHERE id=?', (job_id,))
                db.execute('UPDATE jobs SET completed=completed+1 WHERE id=?', (job_id,))
        with connect() as db: db.execute("UPDATE jobs SET status='done' WHERE id=?", (job_id,))

