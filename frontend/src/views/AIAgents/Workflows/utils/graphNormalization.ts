import { Edge, Node } from 'reactflow';

/**
 * Strips React Flow's transient UI fields (selection, active-drag, measured/derived
 * geometry) so undo and unsaved-changes use the same rules.
 */
export const stripTransientGraphFields = (
  nodes: Node[],
  edges: Edge[]
): { nodes: Node[]; edges: Edge[] } => ({
  nodes: nodes.map(({ selected, dragging, width, height, positionAbsolute, ...node }: Node) => node),
  edges: edges.map(({ selected, className, ...edge }: Edge) => edge),
});
