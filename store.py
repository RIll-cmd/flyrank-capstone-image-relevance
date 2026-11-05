import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from tenancy import database_path

@contextmanager
def connect():
    db = sqlite3.connect(database_path(), timeout=15)
    db.row_factory = sqlite3.Row
    try:
        with db: yield db
    finally: db.close()

def initialize():
    with connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS schema_migrations(version TEXT PRIMARY KEY)')
        for migration in sorted((Path(__file__).parent/'migrations').glob('*.sql')):
            if not db.execute('SELECT 1 FROM schema_migrations WHERE version=?',(migration.name,)).fetchone():
                db.executescript(migration.read_text(encoding='utf8'))
                db.execute('INSERT INTO schema_migrations(version) VALUES(?)',(migration.name,))

        for row in db.execute('SELECT id,metadata FROM images WHERE metadata IS NOT NULL'):
            meta=json.loads(row['metadata'])
            tags=set([meta['subject'],meta['category'],*meta['attributes']])
            db.executemany('INSERT OR IGNORE INTO image_tags(image_id,tag) VALUES(?,?)',[(row['id'],tag) for tag in tags])

def reserve_call():
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        used=db.execute("SELECT COUNT(*) FROM call_reservations WHERE day=date('now')").fetchone()[0]
        if used >= int(os.getenv('MAX_MODEL_CALLS_PER_DAY','500')):raise RuntimeError('Daily model call budget exhausted')
        db.execute("INSERT INTO call_reservations(day) VALUES(date('now'))")

def alert(job_id,image_id,error):
    import logging
    with connect() as db:db.execute('INSERT INTO alerts(job_id,image_id,error) VALUES(?,?,?)',(job_id,image_id,error))
    logging.getLogger('matching').error('Batch image failed job=%s image=%s',job_id,image_id)

def call_log(job_id, operation, model, duration_ms, usage, outcome):
    with connect() as db:
        db.execute('INSERT INTO model_calls(job_id,operation,model,duration_ms,input_tokens,output_tokens,outcome) VALUES(?,?,?,?,?,?,?)', (job_id,operation,model,duration_ms,usage.get('prompt_eval_count'),usage.get('eval_count'),outcome))

def matching_data(post_id):
    with connect() as db:
        post=db.execute('SELECT * FROM posts WHERE id=?',(post_id,)).fetchone()
        rows=db.execute('SELECT * FROM images WHERE metadata IS NOT NULL AND embedding IS NOT NULL').fetchall()
        return post,rows

def save_suggestions(post_id,candidates):
    with connect() as db:
        db.executemany('''INSERT INTO suggestions(post_id,image_id,similarity,accepted,reason) VALUES(?,?,?,?,?)
            ON CONFLICT(post_id,image_id) DO UPDATE SET similarity=excluded.similarity,accepted=excluded.accepted,reason=excluded.reason,updated_at=CURRENT_TIMESTAMP''',
            [(post_id,c['image_id'],c['similarity'],int(c['accepted']),c['reason']) for c in candidates])
