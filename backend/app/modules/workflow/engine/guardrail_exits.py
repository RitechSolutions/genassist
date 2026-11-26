from typing import Any, List, Optional

from .loops import handle_targets

PASSED_HANDLE = "output"
BLOCKED_HANDLE = "output_blocked"


class GuardrailExitMixin:
    """Routes a guardrail node through its Passed or Blocked exit."""

    def exit_to(self, passed: bool, output: dict, stop_output: Optional[dict] = None) -> dict:
        handle = PASSED_HANDLE if passed else BLOCKED_HANDLE
        targets = handle_targets(self.node_id, handle, self.state.source_edges)
        if not passed and not targets:
            return {**(stop_output or output), "passed": False, "next_nodes": []}
        return {**output, "next_nodes": targets}

    def get_bypass_next_nodes(self) -> Optional[List[str]]:
        return handle_targets(self.node_id, PASSED_HANDLE, self.state.source_edges)

    def set_node_output(self, output: Any) -> None:
        if isinstance(output, dict) and "next_nodes" in output:
            if output.get("passed") is False and output["next_nodes"] == []:
                output = output.get("message", "")
            else:
                output = {key: value for key, value in output.items() if key != "next_nodes"}
        super().set_node_output(output)
