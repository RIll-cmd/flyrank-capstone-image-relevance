import json
from PIL import Image
import provider

def test_low_information_image_is_flagged_even_if_model_is_confident(tmp_path, monkeypatch):
    image=tmp_path/'blank.png'
    Image.new('RGB',(32,32),'white').save(image)
    metadata={'subject':'fox','category':'animal','attributes':[],'caption':'A fox','confidence':0.95}
    monkeypatch.setattr(provider,'invoke',lambda *args: {'response':json.dumps(metadata)})
    result=provider.vision(str(image),'job')
    assert result['model_confidence']==0.95
    assert result['confidence'] < 0.75
    assert result['quality_warning']
