from ranking import composition_bonus

def test_portrait_query_prefers_a_caption_describing_a_close_view():
    query='A close view of a red fox face outdoors.'
    assert composition_bonus(query, 'A close-up of a young red fox in grass') > composition_bonus(query, 'Two red foxes in a snowy landscape')

def test_unrelated_query_does_not_receive_portrait_bonus():
    assert composition_bonus('A fox running through snow', 'A close-up of a fox') == 0
