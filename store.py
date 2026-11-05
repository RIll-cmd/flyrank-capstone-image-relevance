import json
import os
import sqlite3
from contextlib import contextmanager

@contextmanager
def connect():
    db = sqlite3.connect(os.getenv('DATABASE_PATH', 'matching.db'), timeout=15)
    db.row_factory = sqlite3.Row
    try:
        with db: yield db
    finally: db.close()

def initialize():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS images(id INTEGER PRIMARY KEY, path TEXT NOT NULL, source TEXT NOT NULL, license TEXT NOT NULL, metadata TEXT, embedding TEXT, status TEXT NOT NULL DEFAULT 'pending', error TEXT);
        CREATE TABLE IF NOT EXISTS posts(id INTEGER PRIMARY KEY, title TEXT NOT NULL, content TEXT NOT NULL, expected_subject TEXT NOT NULL, embedding TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, status TEXT NOT NULL, total INTEGER NOT NULL, completed INTEGER NOT NULL DEFAULT 0, failed INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS model_calls(id INTEGER PRIMARY KEY, job_id TEXT, operation TEXT NOT NULL, model TEXT NOT NULL, duration_ms INTEGER NOT NULL, input_tokens INTEGER, output_tokens INTEGER, cost_usd REAL NOT NULL DEFAULT 0, outcome TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY, post_id INTEGER NOT NULL REFERENCES posts(id), image_id INTEGER NOT NULL REFERENCES images(id), decision TEXT NOT NULL, note TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS image_tags(image_id INTEGER NOT NULL REFERENCES images(id), tag TEXT NOT NULL, PRIMARY KEY(image_id,tag));
        CREATE TABLE IF NOT EXISTS suggestions(post_id INTEGER NOT NULL REFERENCES posts(id), image_id INTEGER NOT NULL REFERENCES images(id), similarity REAL NOT NULL, accepted INTEGER NOT NULL, reason TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(post_id,image_id));
        CREATE INDEX IF NOT EXISTS images_status_idx ON images(status);
        CREATE INDEX IF NOT EXISTS reviews_pair_idx ON reviews(post_id,image_id);
        CREATE INDEX IF NOT EXISTS calls_job_idx ON model_calls(job_id);
        CREATE INDEX IF NOT EXISTS image_tags_tag_idx ON image_tags(tag);
        CREATE INDEX IF NOT EXISTS suggestions_post_idx ON suggestions(post_id,accepted,similarity DESC);
        ''')
        for row in db.execute('SELECT id,metadata FROM images WHERE metadata IS NOT NULL'):
            meta=json.loads(row['metadata'])
            tags=set([meta['subject'],meta['category'],*meta['attributes']])
            db.executemany('INSERT OR IGNORE INTO image_tags(image_id,tag) VALUES(?,?)',[(row['id'],tag) for tag in tags])

def call_log(job_id, operation, model, duration_ms, usage, outcome):
    with connect() as db:
        db.execute('INSERT INTO model_calls(job_id,operation,model,duration_ms,input_tokens,output_tokens,outcome) VALUES(?,?,?,?,?,?,?)', (job_id,operation,model,duration_ms,usage.get('prompt_eval_count'),usage.get('eval_count'),outcome))
