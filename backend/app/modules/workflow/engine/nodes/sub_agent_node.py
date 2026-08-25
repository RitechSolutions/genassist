"""Sub-agent node: a specialist agent a parent delegates to"""

import logging
from typing import Any, Dict, Optional

from pydantic import ValidationError

from app.modules.workflow.agents.agent_runtime import run_agent_once
from app.modules.workflow.agents.sub_agents import messages
from app.modules.workflow.agents.sub_agents.models import SubAgentConfig
from app.modules.workflow.agents.sub_agents.orchestrator import SUB_AGENT_CONTROL_ATTR
from app.modules.workflow.engine.nodes.agent_node import AgentNode

logger = logging.getLogger(__name__)


class SubAgentNode(AgentNode):
    """Child agent invoked by a parent's delegation tool"""

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        invalid = self._validate_config_values(config)
        if invalid:
            return invalid

        provider_id = config.get("providerId")
        fallback_chain_id = config.get("fallbackChainId")
        agent_type = config.get("type", "ToolSelector")
        max_iterations = config.get("maxIterations", 7)
        memory_enabled = config.get("memory", False)
        mode = config.get("mode", "single_turn")
        prompt_caching_enabled = config.get("promptCaching") is True

        system_prompt = config.get("systemPrompt") or "You are a helpful assistant."
        system_prompt += self._completion_instructions(mode)
        prompt = config.get("userPrompt") or "{{session.message}}"

        tools = self.get_connected_nodes("tools")
        from app.modules.workflow.agents.sub_agents.graph import SubAgentTopologyError

        try:
            delegation_tools, delegation_map = self._build_delegation_tools(config)
        except SubAgentTopologyError as e:
            return {"message": f"The sub-agent could not run: {e}", "error": str(e)}

        completion_tool = self._build_completion_tool(mode)
        all_tools = tools + delegation_tools + ([completion_tool] if completion_tool else [])

        if config.get("piiMasking") and all_tools:
            self._wrap_tools_for_pii_unmask(all_tools)

        system_prompt, stable_volatile_parts = self._timestamped_system_prompt(system_prompt)

        self.set_node_input({"system_prompt": system_prompt, "prompt": prompt, "tools_reference": all_tools})

        try:
            chat_history = []
            if memory_enabled:
                chat_history = await self._get_chat_history_for_agent(
                    self.get_memory(), config, provider_id, system_prompt, prompt
                )

            if delegation_map:
                return await self._run_agent_with_delegations(
                    config=config,
                    provider_id=provider_id,
                    fallback_chain_id=fallback_chain_id,
                    agent_type=agent_type,
                    system_prompt=system_prompt,
                    prompt=prompt,
                    all_tools=all_tools,
                    delegation_map=delegation_map,
                    max_iterations=max_iterations,
                    chat_history=chat_history,
                    stable_volatile_parts=stable_volatile_parts,
                    prompt_caching_enabled=prompt_caching_enabled,
                )

            run = await run_agent_once(
                state=self.get_state(),
                node_id=self.node_id,
                provider_id=provider_id,
                fallback_chain_id=fallback_chain_id,
                agent_type=agent_type,
                system_prompt=system_prompt,
                user_prompt=prompt,
                tools=all_tools,
                max_iterations=max_iterations,
                chat_history=chat_history,
                stable_volatile_parts=stable_volatile_parts,
                prompt_caching_enabled=prompt_caching_enabled,
            )
            return self._shape_delegated_output(run, run.steps, run.tools_used)
        except Exception as e:
            logger.exception("Error processing sub-agent node")
            return {"message": messages.child_failed(), "error": str(e)}

    def _validate_config_values(self, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # Provider presence is a runtime-only requirement (drafts save without one)
        if not config.get("providerId"):
            return {"message": "The sub-agent is missing an LLM provider.", "error": "missing providerId"}
        try:
            SubAgentConfig.model_validate(config)
        except ValidationError as exc:
            return self._config_value_error(config, exc)
        return None

    @staticmethod
    def _config_value_error(config: Dict[str, Any], exc: ValidationError) -> Dict[str, Any]:
        err = exc.errors()[0]
        field = err["loc"][0] if err.get("loc") else ""
        if field == "mode":
            return {"message": f"The sub-agent has an invalid mode: {config.get('mode')}.", "error": "invalid mode"}
        if field == "type":
            return {
                "message": f"The sub-agent has an unsupported agent type: {config.get('type')}.",
                "error": "invalid agent type",
            }
        if field == "timeoutSeconds":
            if "between" in err.get("msg", ""):
                return {
                    "message": "The sub-agent timeout must be between 5 and 300 seconds.",
                    "error": "timeout out of range",
                }
            return {"message": "The sub-agent has an invalid timeout.", "error": "invalid timeoutSeconds"}
        return {"message": "The sub-agent configuration is invalid.", "error": "invalid config"}

    @staticmethod
    def _completion_instructions(mode: str) -> str:
        if mode == "task":
            return (
                "\n\nYou are a task sub-agent. Do the requested task. If you need one "
                "clarification from the user, reply with only your question as plain text. "
                "When the task is finished, call the finish_task tool with your final result."
            )
        if mode == "chat":
            return (
                "\n\nYou are a conversational sub-agent and own this conversation until you "
                "hand back. Reply to the user directly. When you are done, call the "
                "return_to_parent tool with a short summary to return control to the main agent."
            )
        return (
            "\n\nYou are a single-turn sub-agent. Give one complete answer to the task and "
            "do not ask the user any questions."
        )

    def _build_completion_tool(self, mode: str):
        """Return the finish_task/return_to_parent tool, or None for single_turn"""
        if mode == "single_turn":
            return None
        from app.modules.workflow.agents.base_tool import BaseTool

        state = self.get_state()
        tool_name = "finish_task" if mode == "task" else "return_to_parent"
        description = (
            "Call this with your final result when the task is complete."
            if mode == "task"
            else "Call this with a summary to return control to the main agent."
        )

        async def _complete(payload: Dict[str, Any]) -> str:
            result = (payload or {}).get("parameters", {}).get("result", "") or ""
            state.set_value(SUB_AGENT_CONTROL_ATTR, {"result": result})
            return result

        return BaseTool(
            node_id=self.node_id,
            name=tool_name,
            description=description,
            parameters={"result": {"type": "string", "description": "Your final result or summary.", "required": True}},
            function=_complete,
            return_direct=True,
        )
