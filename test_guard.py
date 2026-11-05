from guard import assess, cosine

def test_reject_wolf_for_fox_even_at_high_similarity():
    result=assess("red fox", {"subject":"gray wolf", "category":"animal", "confidence":0.99}, 0.99)
    assert not result["accepted"] and "mismatch" in result["reason"].lower()

def test_reject_uncertain():
    assert not assess("red fox", {"subject":"red fox", "category":"animal", "confidence":0.4}, 0.99)["accepted"]

def test_reject_low_similarity():
    assert not assess("red fox", {"subject":"red fox", "category":"animal", "confidence":0.99}, 0.2)["accepted"]

def test_allow_valid():
    assert assess("red fox", {"subject":"red fox", "category":"animal", "confidence":0.99}, 0.9)["accepted"]

def test_cosine_zero_and_identical():
    assert cosine([0,0],[1,1])==0
    assert abs(cosine([1,2],[1,2])-1)<1e-9
