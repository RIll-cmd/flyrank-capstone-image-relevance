import math, re

ALIASES={"vulpes vulpes":"red fox", "red fox":"red fox", "grey wolf":"wolf", "gray wolf":"wolf", "wolf":"wolf", "dog":"dog", "bear":"bear", "deer":"deer"}

def subject(text):
    text=re.sub(r"[^a-z ]", " ", text.lower())
    return next((v for k,v in ALIASES.items() if re.search(r"\b"+re.escape(k)+r"\b", text)), None)

def cosine(a,b):
    if len(a)!=len(b) or not a: return 0.0
    na=math.sqrt(sum(x*x for x in a)); nb=math.sqrt(sum(x*x for x in b))
    return sum(x*y for x,y in zip(a,b))/(na*nb) if na and nb else 0.0

def assess(expected, metadata, similarity, min_similarity=0.72, min_confidence=0.75):
    wanted=subject(expected); observed=subject(metadata.get("subject", ""))
    if metadata.get("confidence",0)<min_confidence: return {"accepted":False,"reason":"Vision confidence below threshold"}
    if not wanted: return {"accepted":False,"reason":"Expected subject is outside the verified subject list"}
    if wanted and observed and wanted!=observed: return {"accepted":False,"reason":f"Subject mismatch: expected {wanted}, detected {observed}"}
    if wanted and not observed: return {"accepted":False,"reason":"Subject could not be verified"}
    if similarity<min_similarity: return {"accepted":False,"reason":"Semantic similarity below threshold"}
    return {"accepted":True,"reason":"Subject, confidence and similarity passed the guard"}
