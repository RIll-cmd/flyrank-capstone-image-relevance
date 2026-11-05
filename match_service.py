import json,os
from guard import cosine,assess
from ranking import composition_bonus
from store import matching_data,save_suggestions

def ranking(post_id):
    post,rows=matching_data(post_id)
    if not post:raise LookupError('Post not found')
    candidates=[]
    for row in rows:
        meta=json.loads(row['metadata'])
        similarity=cosine(json.loads(post['embedding']),json.loads(row['embedding']))
        decision=assess(post['expected_subject'],meta,similarity,float(os.getenv('SIMILARITY_THRESHOLD','0.72')),float(os.getenv('CONFIDENCE_THRESHOLD','0.75')))
        bonus=composition_bonus(post['title']+' '+post['content'],meta['caption'])
        candidates.append({'image_id':row['id'],'metadata':meta,'similarity':round(similarity,4),'rank_score':round(similarity+bonus,4),**decision})
    save_suggestions(post_id,candidates)
    return sorted(candidates,key=lambda c:c['rank_score'],reverse=True)
