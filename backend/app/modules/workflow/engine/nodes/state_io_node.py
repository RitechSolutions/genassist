from typing import Any, Dict, List, Set
import logging

from redis.asyncio import Redis

from app.modules.workflow.engine.base_node import BaseNode
from app.dependencies.injector import injector
from app.dependencies.dependency_injection import RedisString
from app.core.tenant_scope import get_tenant_context

logger = logging.getLogger(__name__)


class StateIONode(BaseNode):
    """
    Node responsible for synchronizing workflow state variables
    with a persistent backend store (Redis).

    Behaviour:
    - Discovers all parameters in the workflow input schemas that have
      shouldPersist = True.
    - Loads their current values from Redis and writes them into the
      workflow session (state.session).
    - Applies explicit overrides defined on this node (stateVariables)
      and writes them back to Redis.
    - Exposes the final state variables as its output.
    """

    async def _get_redis(self) -> Redis:
        """Get Redis client for string data."""
        return injector.get(RedisString)

    def _get_redis_key(self) -> str:
        """
        Build a Redis key for workflow-level state variables.

        Key pattern (tenant-aware):
            tenant:{tenant_id}:workflow:{workflow_id}:thread:{thread_id}:state_vars
        """
        tenant_id = get_tenant_context()
        tenant_prefix = f"tenant:{tenant_id}:" if tenant_id else ""

        workflow_id = (
            self.get_state().workflow_id
            or self.get_state().workflow.get("config", {}).get("id")
        )
        if not workflow_id:
            workflow_id = "unknown"

        thread_id = self.get_state().thread_id or "unknown"

        return f"{tenant_prefix}workflow:{workflow_id}:thread:{thread_id}:state_vars"

    def _discover_persistent_param_names(self) -> Set[str]:
        """
        Scan all workflow nodes to find parameters with shouldPersist = True.

        Currently looks for data.inputSchema entries that declare shouldPersist.
        """
        workflow = self.get_state().workflow
        nodes: List[Dict[str, Any]] = workflow.get("nodes", []) if workflow else []

        persistent_names: Set[str] = set()

        for node in nodes:
            data = node.get("data", {}) or {}
            input_schema = data.get("inputSchema") or {}
            if not isinstance(input_schema, dict):
                continue

            for key, schema_info in input_schema.items():
                try:
                    if isinstance(schema_info, dict) and schema_info.get("shouldPersist"):
                        persistent_names.add(key)
                except Exception:  # pylint: disable=broad-except
                    # Defensive: schema could be arbitrarily shaped
                    continue

        return persistent_names

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synchronize persistent state variables with Redis and workflow session.

        Config structure (from node data):
            {
                "name": ...,
                "stateVariables": { "key": "value", ... },
                ...
            }

        Returns:
            { "state": { "key": "resolved_value", ... } }
        """
        redis = await self._get_redis()
        redis_key = self._get_redis_key()

        # 1) Discover all declared persistent parameters in this workflow
        persistent_param_names = self._discover_persistent_param_names()

        # 2) Collect explicit overrides / additional variables from resolved node config
        # NOTE: `config` here has already had all {{variable}} templates resolved
        #       by BaseNode.execute via replace_config_vars, so we must use it
        #       instead of raw self.get_node_data() to avoid persisting templates.
        overrides: Dict[str, Any] = config.get("stateVariables") or {}
        if not isinstance(overrides, dict):
            overrides = {}

        # Ensure override keys are included in the final set of names we manage
        all_managed_names: Set[str] = set(persistent_param_names) | set(overrides.keys())

        # 3) Load existing values from Redis
        stored_values: Dict[str, Any] = {}
        try:
            if all_managed_names:
                # hgetall returns {} for non-existing keys when decode_responses=True
                stored_values = await redis.hgetall(redis_key)  # type: ignore[assignment]
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Failed to read state variables from Redis: %s", exc)
            stored_values = {}

        # 4) Resolve final values (overrides win over stored values)
        resolved_state: Dict[str, Any] = {}
        for name in all_managed_names:
            if name in overrides and overrides[name] not in (None, ""):
                resolved_state[name] = overrides[name]
            else:
                value = stored_values.get(name)
                if value not in (None, ""):
                    resolved_state[name] = value

        # 5) Persist the updated values back to Redis (only non-empty)
        try:
            to_persist = {
                key: str(value)
                for key, value in resolved_state.items()
                if value not in (None, "")
            }
            if to_persist:
                await redis.hset(redis_key, mapping=to_persist)  # type: ignore[arg-type]
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Failed to write state variables to Redis: %s", exc)

        # 6) Update workflow session so other nodes can consume these values
        for key, value in resolved_state.items():
            self.get_state().update_session_value(key, value)

        # 7) Expose state as node output
        output = {"state": resolved_state}
        self.set_node_input({})
        self.set_node_output(output)

        logger.debug(
            "StateIONode %s synchronized variables: %s", self.node_id, list(resolved_state.keys())
        )

        return output

