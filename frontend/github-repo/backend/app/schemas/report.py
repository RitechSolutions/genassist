from typing import Dict
from pydantic import BaseModel, ConfigDict
class TopicsReport(BaseModel):
    total: int
    details: Dict[str, int]