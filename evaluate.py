import json
import os
from pathlib import Path
import requests

base=os.getenv('BASE_URL','http://127.0.0.1:8000').rstrip('/')
labels=json.loads((Path(__file__).parent/'evals'/'labels.json').read_text(encoding='utf8'))
if len(labels)<10: raise SystemExit('At least 10 labeled posts are required')
correct=0
for case in labels:
    response=requests.get(f"{base}/posts/{case['post_id']}/images",timeout=30); response.raise_for_status()
    suggestions=response.json()['suggestions']
    actual=suggestions[0]['image_id'] if suggestions else None
    ok=actual==case['expected_image_id']; correct+=ok
    print(f"{case['title']}: expected={case['expected_image_id']} actual={actual} {'PASS' if ok else 'MISS'}")
print(f'Top-1 precision: {correct}/{len(labels)} = {correct/len(labels):.3f}; refusals count as misses')
