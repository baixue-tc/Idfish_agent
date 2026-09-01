from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    message:Optional[str] = None
    user_id:str
    product_id:str

class ChatResponse(BaseModel):
    message:Optional[str] = None
    user_id: str
    product_id: str


