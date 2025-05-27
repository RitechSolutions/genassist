from app.db.models import AgentModel
from app.schemas.agent import AgentRead


def to_agent_read(model: AgentModel) -> AgentRead:
    return AgentRead(
            **model.__dict__,
            tool_ids=[t.tool_id for t in model.agent_tools],
            knowledge_base_ids=[
                kb.knowledge_base_id for kb in model.agent_knowledge_bases
                ],
            )
