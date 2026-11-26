"""
Generate the Workflow Builder agent's own workflow (workflow_builder_wf_data.json).

Usage:
    python -m app.db.seed.knowledge.generate_workflow_builder_workflow

The workflow is small: Chat Input -> Workflow Builder agent -> Chat Output, with
one Workflow Builder Tools node attached to the agent. Its system prompt lives
in ``workflow_builder_prompt.md``; the node index at the end of the prompt is
filled in from the node catalog, so regenerate after adding node types.
"""

import json
from pathlib import Path
from typing import Any, Dict

from app.db.seed.seed_data_config import seed_test_data
from app.modules.workflow.builder import catalog
from app.modules.workflow.builder.draft import make_edge

SEED_DIR = Path(__file__).resolve().parent.parent
PROMPT_PATH = SEED_DIR / "workflow_builder_prompt.md"
OUTPUT_PATH = SEED_DIR / "workflow_builder_wf_data.json"

# The builder runs on the provider seed.py creates for it (migration 00130 adds it to
# tenants seeded earlier). Its id is fixed, so the seeded JSON names it directly.
DEFAULT_PROVIDER_ID = seed_test_data.workflow_builder_llm_provider_id

CHAT_INPUT_ID = "wb-chat-input-001"
AGENT_ID = "wb-agent-builder"
TOOLS_ID = "wb-builder-tools"
CHAT_OUTPUT_ID = "wb-chat-output"


def build_system_prompt() -> str:
    prompt = PROMPT_PATH.read_text(encoding="utf-8").strip()
    return prompt.replace("{NODE_INDEX}", catalog.compact_index(names_only=True))


def _node(node_id: str, node_type: str, x: int, y: int, **data: Any) -> Dict[str, Any]:
    node_data = catalog.default_data(node_type)
    node_data.update(data)
    node_data.setdefault("label", catalog.label(node_type))
    node_data["handlers"] = catalog.handlers_for(node_type, node_data)
    return {
        "id": node_id,
        "type": node_type,
        "position": {"x": x, "y": y},
        "positionAbsolute": {"x": x, "y": y},
        "data": node_data,
    }


def build_workflow(provider_id: str = DEFAULT_PROVIDER_ID) -> Dict[str, Any]:
    nodes = [
        _node(CHAT_INPUT_ID, "chatInputNode", 0, 200, name="Chat Input"),
        _node(
            AGENT_ID, "agentNode", 400, 200,
            name="Workflow Builder",
            type="ReActAgentLC",
            providerId=provider_id,
            systemPrompt=build_system_prompt(),
            userPrompt="{{session.message}}",
            memory=True,
            memoryTrimmingMode="message_count",
            maxMessages=20,
            # Model calls per message. A normal turn is three (plan, test, reply); the
            # worst case the test-loop guards allow is about a dozen. The last call is
            # forced to be a reply, so a runaway turn ends with an answer, not an error.
            maxIterations=16,
            promptCaching=True,
        ),
        _node(TOOLS_ID, "workflowBuilderToolsNode", 300, 520, name="Workflow Builder Tools"),
        _node(CHAT_OUTPUT_ID, "chatOutputNode", 800, 200, name="Chat Output"),
    ]
    edges = [
        make_edge(CHAT_INPUT_ID, AGENT_ID, "output", "input"),
        make_edge(AGENT_ID, CHAT_OUTPUT_ID, "output", "input"),
        make_edge(TOOLS_ID, AGENT_ID, "output_tool", "input_tools"),
    ]
    return {
        "name": "Workflow Builder Agent",
        "description": "AI agent that creates and edits workflows from natural language",
        "nodes": nodes,
        "edges": edges,
        "testInput": {},
        "executionState": {"source": "", "session": {"message": ""}, "nodeOutputs": {}},
        "version": "2.0",
    }


def main() -> None:
    OUTPUT_PATH.write_text(json.dumps(build_workflow(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
