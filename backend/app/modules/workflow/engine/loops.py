"""
Loop topology shared by the Loop node, the engine and save-time validation.

A Loop node owns a *body*: the nodes reachable from its ``output_loop`` handle.
The last body node wires back into the Loop's ``input_loop`` handle; that
back-edge is the only kind of cycle a workflow may contain. Everything after
the loop hangs off ``output_done``.

    upstream ──input──▶ Loop ──output_loop──▶ body … ──┐
                         ▲  └─output_done──▶ after      │
                         └────────input_loop────────────┘

Handles are matched exactly, never by substring.
"""

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

LOOP_NODE_TYPE = "loopNode"
LOOP_BODY_HANDLE = "output_loop"
LOOP_DONE_HANDLE = "output_done"
LOOP_BACK_HANDLE = "input_loop"

# Pausing inside a body cannot be resumed: a resume starts a fresh run at the
# paused node, so the loop's position (item, iteration, collected results) is lost.
NODE_TYPES_NOT_ALLOWED_IN_LOOP = frozenset({"humanInTheLoopNode"})

# A body node can also pause through what is attached to it: a task/chat
# sub-agent hands the conversation to the user, and a tool's sub-flow can reach
# a node that pauses. A single-turn sub-agent answers within the pass.
_SUB_AGENT_NODE_TYPE = "subAgentNode"
_INTERACTIVE_SUB_AGENT_MODES = frozenset({"task", "chat"})

# Handle of the child → parent delegation edge; never part of the main flow.
_SUB_AGENT_HANDLE = "output_sub_agent"
# Target handles through which a tool or a sub-agent is attached to an agent.
_ATTACHMENT_HANDLES = frozenset({"input_tools", "input_sub_agents"})


class LoopTopologyError(ValueError):
    """A Loop node is wired in a way the engine cannot run."""


def is_loop_back_edge(edge: Dict[str, Any]) -> bool:
    """Whether an edge returns from a loop body into its Loop node."""
    return edge.get("targetHandle") == LOOP_BACK_HANDLE


def handle_targets(loop_id: str, handle: str, source_edges: Dict[str, List[dict]]) -> List[str]:
    """Nodes connected to one of the Loop's output handles, in edge order."""
    targets: List[str] = []
    for edge in source_edges.get(loop_id, []):
        target = edge.get("target")
        if edge.get("sourceHandle") == handle and target and target not in targets:
            targets.append(target)
    return targets


def back_edge_sources(loop_id: str, target_edges: Dict[str, List[dict]]) -> List[str]:
    """Body nodes wired back into the Loop; their output is the iteration's result."""
    sources: List[str] = []
    for edge in target_edges.get(loop_id, []):
        source = edge.get("source")
        if is_loop_back_edge(edge) and source and source not in sources:
            sources.append(source)
    return sources


def reachable_from(
    start_ids: Iterable[str],
    source_edges: Dict[str, List[dict]],
    blocked: Optional[Set[str]] = None,
) -> Set[str]:
    """Nodes the flow reaches from ``start_ids`` without following a back-edge
    or entering a ``blocked`` node."""
    blocked = blocked or set()
    seen: Set[str] = set()
    stack = [node_id for node_id in start_ids if node_id not in blocked]
    while stack:
        node_id = stack.pop()
        if node_id in seen:
            continue
        seen.add(node_id)
        for edge in source_edges.get(node_id, []):
            if is_loop_back_edge(edge) or edge.get("sourceHandle") == _SUB_AGENT_HANDLE:
                continue
            target = edge.get("target")
            if target and target not in blocked and target not in seen:
                stack.append(target)
    return seen


def loop_body(loop_id: str, source_edges: Dict[str, List[dict]]) -> Set[str]:
    """Every node that runs once per iteration of this Loop (nested loops included)."""
    return reachable_from(handle_targets(loop_id, LOOP_BODY_HANDLE, source_edges), source_edges, {loop_id})


def pausing_node_in_body(
    loop_id: str,
    body: Set[str],
    nodes_by_id: Dict[Any, dict],
    source_edges: Dict[str, List[dict]],
    target_edges: Dict[str, List[dict]],
) -> Optional[Tuple[str, str]]:
    """A node that can pause the run during a pass, as ``(node, body node)``.

    Looks at the body and at everything its nodes run on demand: the tools and
    sub-agents attached to them, and the tools' sub-flows. ``body node`` is the
    one it is reached from (the node itself when it sits in the body).
    """
    owner: Dict[str, str] = {}
    stack = [(node_id, node_id) for node_id in sorted(body, reverse=True)]
    while stack:
        node_id, body_node = stack.pop()
        if node_id in owner or node_id == loop_id:
            continue
        owner[node_id] = body_node

        node = nodes_by_id.get(node_id) or {}
        node_type = node.get("type")
        interactive = (
            node_type == _SUB_AGENT_NODE_TYPE and (node.get("data") or {}).get("mode") in _INTERACTIVE_SUB_AGENT_MODES
        )
        if node_type in NODE_TYPES_NOT_ALLOWED_IN_LOOP or interactive:
            return node_id, body_node

        for edge in target_edges.get(node_id, []):
            if edge.get("targetHandle") in _ATTACHMENT_HANDLES and edge.get("source"):
                stack.append((edge["source"], body_node))
        if node_id in body:
            continue  # its main-flow successors are body nodes already
        for edge in source_edges.get(node_id, []):
            # Follow a tool's sub-flow, but not the edge that attaches it to an agent.
            if is_loop_back_edge(edge) or edge.get("targetHandle") in _ATTACHMENT_HANDLES:
                continue
            if edge.get("target"):
                stack.append((edge["target"], body_node))
    return None


def _source_edge_map(edges: Optional[List[dict]]) -> Dict[str, List[dict]]:
    mapping: Dict[str, List[dict]] = defaultdict(list)
    for edge in edges or []:
        if edge.get("source"):
            mapping[edge["source"]].append(edge)
    return mapping


def validate_loop_topology(nodes: Optional[List[dict]], edges: Optional[List[dict]]) -> None:
    """Reject loop wiring the engine cannot run. A no-op for workflows without a Loop.

    Unfinished loops (nothing connected yet) still save, so a draft is never blocked.
    """
    nodes = nodes or []
    loops = [node for node in nodes if node.get("type") == LOOP_NODE_TYPE]
    if not loops:
        return

    by_id = {node.get("id"): node for node in nodes}
    source_edges = _source_edge_map(edges)
    target_edges: Dict[str, List[dict]] = defaultdict(list)
    for edge in edges or []:
        if edge.get("target"):
            target_edges[edge["target"]].append(edge)

    def name_of(node_id: str) -> str:
        node = by_id.get(node_id) or {}
        return (node.get("data") or {}).get("name") or node_id

    for loop in loops:
        loop_id = loop.get("id")
        loop_name = name_of(loop_id)
        body = loop_body(loop_id, source_edges)

        for source in back_edge_sources(loop_id, target_edges):
            if source not in body:
                raise LoopTopologyError(
                    f"'{loop_name}': '{name_of(source)}' is connected to Loop back but is not part of this "
                    "loop's body. Only a node that runs inside the loop can connect back."
                )

        pausing = pausing_node_in_body(loop_id, body, by_id, source_edges, target_edges)
        if pausing and pausing[0] == pausing[1]:
            raise LoopTopologyError(
                f"'{loop_name}': '{name_of(pausing[0])}' pauses the workflow for user input, which is not "
                "supported inside a loop. Move it before the loop or after Done."
            )
        if pausing:
            raise LoopTopologyError(
                f"'{loop_name}': '{name_of(pausing[0])}' pauses the workflow for user input, which is not "
                f"supported inside a loop, and '{name_of(pausing[1])}' in the loop's body uses it. Detach it, "
                "or move that node before the loop or after Done."
            )

        after = reachable_from(handle_targets(loop_id, LOOP_DONE_HANDLE, source_edges), source_edges, {loop_id})
        shared = sorted(body & after)
        if shared:
            raise LoopTopologyError(
                f"'{loop_name}': '{name_of(shared[0])}' is reached both from inside the loop and from Done. "
                "Nodes that run after the loop must be connected from Done only."
            )
