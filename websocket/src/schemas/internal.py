

from pydantic import BaseModel

class AgentExecuteRequest(BaseModel):
    agent_id: str
    thread_id: str
    text: str
