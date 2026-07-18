"""SubAgentNode is registered with the workflow engine"""

from app.modules.workflow.engine.nodes import SubAgentNode
from app.modules.workflow.engine.nodes.agent_node import AgentNode
from app.modules.workflow.engine.workflow_engine import WorkflowEngine


def test_sub_agent_node_registered():
    WorkflowEngine._initialize_node_registry()
    assert WorkflowEngine._node_registry.get("subAgentNode") is SubAgentNode


def test_sub_agent_node_subclasses_agent_node():
    assert issubclass(SubAgentNode, AgentNode)
