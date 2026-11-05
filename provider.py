import base64
import io
import json
import os
import time
from pathlib import Path
import requests
from PIL import Image, ImageOps
from models import VisionMetadata
from store import call_log

def invoke(path, payload, job_id, operation):
    base = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/')
    started = time.monotonic()
    result = {}
    outcome = 'error'
    try:
        response = requests.post(base + path, json=payload, timeout=float(os.getenv('OLLAMA_TIMEOUT_SECONDS','120')))
        response.raise_for_status()
        result = response.json()
        outcome = 'ok'
        return result
    finally:
        call_log(job_id, operation, payload['model'], round((time.monotonic()-started)*1000), result, outcome)

def vision(path, job_id):
    model = os.getenv('VISION_MODEL', 'moondream')
    if Path(path).stat().st_size > 10_000_000: raise ValueError('Image exceeds 10 MB')
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert('RGB')
        limit=640 if model.startswith('moondream') else 256
        image.thumbnail((limit,limit))
        buffer=io.BytesIO(); image.save(buffer,format='JPEG',quality=90)
        data=buffer.getvalue()
    prompt=('Describe only visible content. Give a precise subject, a category, at most four short distinct attributes, a short caption, and confidence from 0 to 1. Do not guess a species.' if model.startswith('moondream') else 'Describe this photograph for an image retrieval library. Identify the most specific visible animal species if recognizable, otherwise use the broader animal name. Include 2-4 distinct visual features and a natural concise caption. Set confidence between 0 and 1 to reflect uncertainty.')
    result = invoke('/api/generate', {'model':model, 'stream':False, 'format':VisionMetadata.model_json_schema(), 'options':{'temperature':0, 'num_predict':180, 'num_ctx':2048}, 'prompt':prompt, 'images':[base64.b64encode(data).decode()]}, job_id, 'vision')
    return VisionMetadata.model_validate_json(result['response']).model_dump()

def embed(text, job_id=None):
    model = os.getenv('EMBED_MODEL', 'all-minilm')
    result = invoke('/api/embed', {'model':model, 'input':text}, job_id, 'embedding')
    values = result['embeddings'][0]
    if not isinstance(values, list) or not values: raise ValueError('Embedding is empty')
    return [float(x) for x in values]
