"""
Auto-layout for generated workflows.

Positions nodes in a left-to-right DAG layout using topological sort.
Special handling for toolBuilderNode which connects via the tools port
and should be placed above its target agentNode. Sub-agent children
(output_sub_agent -> input_sub_agents) are treated the same way: they hang
off their parent agent rather than sitting in the main flow.
"""

from collections import defaultdict, deque
from typing import Dict, List, Any, Set, Tuple

# Layout constants
X_SPACING = 500  # horizontal distance between layers
Y_SPACING = 300  # vertical distance between nodes in the same layer
X_OFFSET = 50    # left margin
Y_OFFSET = 150   # top margin


def _find_back_edges(order: List[str], children: Dict[str, List[str]]) -> List[Tuple[str, str]]:
    """Edges (source, target) that close a cycle, found by iterative DFS."""
    WHITE, GREY, BLACK = 0, 1, 2
    color: Dict[str, int] = defaultdict(int)
    back_edges: List[Tuple[str, str]] = []
    for root in order:
        if color[root] != WHITE:
            continue
        color[root] = GREY
        stack = [(root, iter(children.get(root, [])))]
        while stack:
            current, pending = stack[-1]
            advanced = False
            for child in pending:
                if color[child] == WHITE:
                    color[child] = GREY
                    stack.append((child, iter(children.get(child, []))))
                    advanced = True
                    break
                if color[child] == GREY:
                    back_edges.append((current, child))
            if not advanced:
                color[current] = BLACK
                stack.pop()
    return back_edges


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

        if src_handle in ("output_tool", "output_sub_agent") or tgt_handle in ("input_tools", "input_sub_agents"):
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
        elif src_handle == "output_sub_agent" and tgt_handle == "input_sub_agents":
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

    # Longest-path layering over the main flow. Edges that close a cycle (a loop
    # node's back-edge, or a mistake in a generated spec) are left out, otherwise
    # the relaxation below would never settle.
    back_edges = set(_find_back_edges(roots + list(node_ids), main_children))
    layers: Dict[str, int] = {root: 0 for root in roots}
    queue = deque(roots)
    while queue:
        node_id = queue.popleft()
        current_layer = layers[node_id]
        for child in main_children.get(node_id, []):
            if (node_id, child) in back_edges:
                continue
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

    pending = set(tool_agent_targets)
    progress = True
    while pending and progress:
        progress = False
        for tb_id in sorted(pending):
            agent_id = tool_agent_targets[tb_id]
            if agent_id not in positions:
                continue
            agent_x, agent_y = positions[agent_id]
            # Count how many attachments target this parent
            sibling_tools = [tid for tid, aid in tool_agent_targets.items() if aid == agent_id]
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

            pending.discard(tb_id)
            progress = True

    # Attachments whose parent never got positioned go at the end
    for tb_id in pending:
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


# Spacing used when adding nodes to a canvas the user already arranged; matches
# the gaps the canvas itself uses when it drops a node next to another.
PLACE_X_GAP = 350
PLACE_Y_GAP = 200


def place_new_nodes(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    new_ids: Set[str],
) -> List[Dict[str, Any]]:
    """
    Position only the nodes in ``new_ids``, next to what they are connected to.

    Existing nodes keep the positions the user gave them. New nodes are placed at
    the canvas root, so positions of grouped neighbours are resolved to absolute
    coordinates first.
    """
    by_id = {n["id"]: n for n in nodes}

    def absolute(node: Dict[str, Any]) -> Tuple[float, float]:
        x = (node.get("position") or {}).get("x", 0)
        y = (node.get("position") or {}).get("y", 0)
        parent = by_id.get(node.get("parentId") or node.get("parentNode") or "")
        if parent:
            px, py = absolute(parent)
            return x + px, y + py
        return x, y

    placed: Dict[str, Tuple[float, float]] = {
        n["id"]: absolute(n) for n in nodes if n["id"] not in new_ids and n.get("type") != "groupNode"
    }

    def free_spot(x: float, y: float) -> Tuple[float, float]:
        while any(abs(px - x) < 200 and abs(py - y) < 150 for px, py in placed.values()):
            y += PLACE_Y_GAP
        return x, y

    def anchor_for(node_id: str):
        for edge in edges:
            source, target = edge.get("source"), edge.get("target")
            source_handle = edge.get("sourceHandle") or "output"
            if target == node_id and source in placed:
                sx, sy = placed[source]
                if source_handle == "starter_processor":
                    return sx + PLACE_X_GAP, sy
                return sx + PLACE_X_GAP, sy
            if source == node_id and target in placed:
                tx, ty = placed[target]
                if source_handle in ("output_tool", "output_sub_agent"):
                    return tx - 100, ty + 300
                return tx - PLACE_X_GAP, ty
        return None

    pending = [n["id"] for n in nodes if n["id"] in new_ids]
    progress = True
    while pending and progress:
        progress = False
        for node_id in list(pending):
            spot = anchor_for(node_id)
            if spot is None:
                continue
            placed[node_id] = free_spot(*spot)
            pending.remove(node_id)
            progress = True

    for node_id in pending:
        right = max((x for x, _ in placed.values()), default=X_OFFSET - PLACE_X_GAP)
        top = min((y for _, y in placed.values()), default=Y_OFFSET)
        placed[node_id] = free_spot(right + PLACE_X_GAP, top)

    for node in nodes:
        if node["id"] in new_ids:
            x, y = placed[node["id"]]
            node["position"] = {"x": x, "y": y}
            node["positionAbsolute"] = {"x": x, "y": y}
    return nodes
