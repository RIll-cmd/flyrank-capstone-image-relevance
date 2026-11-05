"""Register the downloaded corpus and a small manually labelled evaluation set."""
import json
import os
from pathlib import Path
import requests

base=os.getenv('BASE_URL','http://127.0.0.1:8000').rstrip('/')
root=Path(__file__).parent
corpus=json.loads((root/'corpus.json').read_text(encoding='utf8'))

def post(path,data):
    result=requests.post(base+path,json=data,timeout=70)
    result.raise_for_status()
    return result.json()

ids=[]
for item in corpus:
    ids.append(post('/images',{'path':item['path'],'source':item['source'],'license':item['license']})['id'])

# Gold labels refer to visually inspected image positions in contact-sheet.jpg.
cases=[
 ('A red fox portrait','A close view of a red fox face outdoors.','red fox',0),
 ('A fox at rest','A red fox rests on grass among trees.','red fox',3),
 ('Fox in snow','A red fox moves through white snow.','red fox',4),
 ('Young fox portrait','A young red fox is seen close up.','red fox',7),
 ('A wolf portrait','A gray wolf looks forward.','wolf',10),
 ('Wolf in winter','A gray wolf stands in snow among trees.','wolf',15),
 ('Black dog profile','A black domestic dog wearing a green collar.','dog',22),
 ('Large dog portrait','A close portrait of a large tan domestic dog.','dog',25),
 ('Brown bear near water','A brown bear standing beside a shallow river.','bear',30),
 ('Brown bear close up','A close view of the face of a brown bear.','bear',32),
]
labels=[]
for title,content,subject,index in cases:
    result=post('/posts',{'title':title,'content':content,'expected_subject':subject})
    labels.append({'post_id':result['id'],'expected_image_id':ids[index],'title':title})
(root/'evals'/'labels.json').write_text(json.dumps(labels,indent=2),encoding='utf8')
print(f'Registered {len(ids)} images and {len(labels)} labeled posts. Start POST /jobs to classify images.')
