from pydantic import BaseModel, Field

class VisionMetadata(BaseModel):
    subject: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=80)
    attributes: list[str] = Field(max_length=4)
    caption: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)

class PostIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=10000)
    expected_subject: str = Field(min_length=1, max_length=120)

class ImageIn(BaseModel):
    path: str = Field(min_length=1, max_length=1000)
    source: str = Field(min_length=1, max_length=1000)
    license: str = Field(min_length=1, max_length=500)

class ReviewIn(BaseModel):
    decision: str
    note: str = Field(default='', max_length=1000)
