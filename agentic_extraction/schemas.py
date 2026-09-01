from pydantic import BaseModel
from typing import List

class CommonsenseKnowledge(BaseModel):
    color: List[str]
    shape: List[str]
    material: List[str]
    function: List[str]