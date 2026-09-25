import { Node } from "reactflow";
import nodeRegistry from "../registry/nodeRegistry";

export const getNodeDisplayName = (node: Node): string =>
  (node.data?.name as string | undefined) ||
  nodeRegistry.getNodeType(node.type ?? "")?.label ||
  "node";

export const buildDeleteConfirmation = (
  nodes: Node[]
): { itemName: string; description?: string } =>
  nodes.length === 1
    ? { itemName: getNodeDisplayName(nodes[0]) }
    : {
        itemName: "",
        description: `This action cannot be undone. This will permanently delete ${nodes.length} nodes.`,
      };
