import re

_CLOSE_VIEW = re.compile(r'\b(?:close[ -]?up|close view|portrait)\b',re.I)

def composition_bonus(query, caption):
    """Prefer close-view captions when the article explicitly asks for one."""
    return 0.02 if _CLOSE_VIEW.search(query) and _CLOSE_VIEW.search(caption) else 0.0
