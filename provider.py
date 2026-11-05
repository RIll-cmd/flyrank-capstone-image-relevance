import base64
import json
import os
import time
from pathlib import Path
import requests
from models import VisionMetadata
from store import call_log

def invoke(path, payload, job_id, operation):
    base = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/')
    started = time.monotonic()
    result = {}
    outcome = 'error'
    try:
        response = requests.post(base + path, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        outcome = 'ok'
        return result
    finally:
        call_log(job_id, operation, payload['model'], round((time.monotonic()-started)*1000), result, outcome)

def vision(path, job_id):
    data = Path(path).read_bytes()
    if len(data) > 10_000_000: raise ValueError('Image exceeds 10 MB')
    model = os.getenv('VISION_MODEL', 'moondream')
    result = invoke('/api/generate', {'model':model, 'stream':False, 'format':VisionMetadata.model_json_schema(), 'options':{'temperature':0, 'num_predict':160}, 'prompt':'Describe only visible content. Give a precise subject, a category, at most four short distinct attributes, a short caption, and confidence from 0 to 1. Do not guess a species.', 'images':[base64.b64encode(data).decode()]}, job_id, 'vision')
    return VisionMetadata.model_validate_json(result['response']).model_dump()

def embed(text, job_id=None):
    model = os.getenv('EMBED_MODEL', 'all-minilm')
    result = invoke('/api/embed', {'model':model, 'input':text}, job_id, 'embedding')
    values = result['embeddings'][0]
    if not isinstance(values, list) or not values: raise ValueError('Embedding is empty')
    return [float(x) for x in values]
