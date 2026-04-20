"""
Auto-layout for generated workflows.

Positions nodes in a left-to-right DAG layout using topological sort.
Special handling for toolBuilderNode which connects via the tools port
and should be placed above its target agentNode.
"""

from collections import defaultdict, deque
from typing import Dict, List, Any, Set, Tuple

# Layout constants
X_SPACING = 500  # horizontal distance between layers
Y_SPACING = 300  # vertical distance between nodes in the same layer
X_OFFSET = 50    # left margin
Y_OFFSET = 150   # top margin


def auto_layout(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Apply left-to-right DAG layout to workflow nodes.

    Args:
        nodes: List of node dicts (must have "id" field)
        edges: List of edge dicts (must have "source", "target", and optionally
               "sourceHandle"/"targetHandle" fields)

    Returns:
        The same nodes list with updated position and positionAbsolute fields.
    """
    if not nodes:
        return nodes

    node_ids = {n["id"] for n in nodes}

    # Build adjacency (only for main flow edges, not tool edges)
    main_children: Dict[str, List[str]] = defaultdict(list)
    main_parents: Dict[str, List[str]] = defaultdict(list)
    tool_edges: List[Dict[str, Any]] = []

    for edge in edges:
        src = edge.get("source", "")
        tgt = edge.get("target", "")
        if src not in node_ids or tgt not in node_ids:
            continue

        src_handle = edge.get("sourceHandle", "output")
        tgt_handle = edge.get("targetHandle", "input")

        # Tool connections are handled separately
        if src_handle == "output_tool" or tgt_handle == "input_tools":
            tool_edges.append(edge)
            continue

        # starter_processor edges (toolBuilder -> subflow) also separate
        if src_handle == "starter_processor":
            tool_edges.append(edge)
            continue

        main_children[src].append(tgt)
        main_parents[tgt].append(src)

    # Find roots (nodes with no main-flow parents)
    roots = [nid for nid in node_ids if not main_parents.get(nid)]

    # Identify tool-related nodes (toolBuilderNodes and their subflow targets)
    tool_builder_ids: Set[str] = set()
    tool_subflow_ids: Set[str] = set()
    tool_agent_targets: Dict[str, str] = {}  # toolBuilderId -> agentNodeId

    for edge in tool_edges:
        src = edge.get("source", "")
        tgt = edge.get("target", "")
        src_handle = edge.get("sourceHandle", "")
        tgt_handle = edge.get("targetHandle", "")

        if src_handle == "output_tool" and tgt_handle == "input_tools":
            tool_builder_ids.add(src)
            tool_agent_targets[src] = tgt
        elif src_handle == "starter_processor":
            tool_builder_ids.add(src)
            tool_subflow_ids.add(tgt)

    # Remove tool-related nodes from roots (they'll be positioned relative to their agent)
    roots = [r for r in roots if r not in tool_builder_ids and r not in tool_subflow_ids]

    # If no roots found, fall back to the first node
    if not roots:
        roots = [nodes[0]["id"]]

    # BFS to assign layers
    layers: Dict[str, int] = {}
    queue = deque(roots)
    for root in roots:
        if root not in layers:
            layers[root] = 0

    while queue:
        node_id = queue.popleft()
        current_layer = layers[node_id]
        for child in main_children.get(node_id, []):
            if child in tool_builder_ids or child in tool_subflow_ids:
                continue
            new_layer = current_layer + 1
            if child not in layers or layers[child] < new_layer:
                layers[child] = new_layer
                queue.append(child)

    # Group nodes by layer
    layer_groups: Dict[int, List[str]] = defaultdict(list)
    for nid, layer in layers.items():
        layer_groups[layer].append(nid)

    # Assign positions for main-flow nodes
    positions: Dict[str, Tuple[float, float]] = {}
    for layer_idx in sorted(layer_groups.keys()):
        group = layer_groups[layer_idx]
        x = layer_idx * X_SPACING + X_OFFSET
        for row_idx, nid in enumerate(group):
            y = row_idx * Y_SPACING + Y_OFFSET
            positions[nid] = (x, y)

    # Position tool builder nodes and their subflows relative to their agent
    for tb_id, agent_id in tool_agent_targets.items():
        if agent_id in positions:
            agent_x, agent_y = positions[agent_id]
            # Count how many tool builders target this agent (for vertical stacking)
            sibling_tools = [
                tid for tid, aid in tool_agent_targets.items()
                if aid == agent_id
            ]
            tool_index = sibling_tools.index(tb_id)
            tb_x = agent_x - 100
            tb_y = agent_y + 400 + (tool_index * Y_SPACING)
            positions[tb_id] = (tb_x, tb_y)

            # Position subflow nodes connected via starter_processor
            for edge in tool_edges:
                if (edge.get("source") == tb_id
                        and edge.get("sourceHandle") == "starter_processor"):
                    subflow_id = edge.get("target", "")
                    if subflow_id in node_ids:
                        positions[subflow_id] = (tb_x + X_SPACING, tb_y)
        else:
            # Agent not in main flow, place tool builder at end
            max_layer = max(layer_groups.keys()) if layer_groups else 0
            positions[tb_id] = (
                (max_layer + 1) * X_SPACING + X_OFFSET,
                Y_OFFSET,
            )

    # Any remaining unpositioned nodes (edge cases)
    unpositioned = [nid for nid in node_ids if nid not in positions]
    if unpositioned:
        max_layer = max(layers.values()) if layers else 0
        for i, nid in enumerate(unpositioned):
            positions[nid] = (
                (max_layer + 2) * X_SPACING + X_OFFSET,
                i * Y_SPACING + Y_OFFSET,
            )

    # Apply positions to nodes
    for node in nodes:
        nid = node["id"]
        if nid in positions:
            x, y = positions[nid]
            node["position"] = {"x": x, "y": y}
            node["positionAbsolute"] = {"x": x, "y": y}

    return nodes
