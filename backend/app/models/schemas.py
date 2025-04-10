import datetime
from pydantic import BaseModel
from typing import Optional, Dict, Any

class User(BaseModel):
    id: int
    username: str
    role: str
    conf: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    
    class Config:
        orm_mode = True 