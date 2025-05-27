import { Node } from 'reactflow';
import { NodeTypeDefinition, createNode } from '../types/nodes';

// Registry for all node types
class NodeRegistry {
  private nodeTypes: Map<string, NodeTypeDefinition> = new Map();
  private nodeCategories: Map<string, NodeTypeDefinition[]> = new Map();

  // Register a new node type
  register(nodeType: NodeTypeDefinition): void {
    this.nodeTypes.set(nodeType.type, nodeType);
    
    // Add to categories
    if (!this.nodeCategories.has(nodeType.category)) {
      this.nodeCategories.set(nodeType.category, []);
    }
    this.nodeCategories.get(nodeType.category)?.push(nodeType);
  }

  // Alias for register to match new code
  registerNodeType(nodeType: NodeTypeDefinition): void {
    this.register(nodeType);
  }

  // Clear the registry
  clearRegistry(): void {
    this.nodeTypes.clear();
    this.nodeCategories.clear();
  }

  // Get a node type by type name
  getNodeType(type: string): NodeTypeDefinition | undefined {
    return this.nodeTypes.get(type);
  }

  // Get all node types
  getAllNodeTypes(): NodeTypeDefinition[] {
    return Array.from(this.nodeTypes.values());
  }

  // Get node types by category
  getNodeTypesByCategory(category: string): NodeTypeDefinition[] {
    return this.nodeCategories.get(category) || [];
  }

  // Get all categories
  getAllCategories(): string[] {
    return Array.from(this.nodeCategories.keys());
  }

  // Create a new node instance
  createNode(type: string, id: string, position: { x: number; y: number }, overrideData?: Record<string, unknown>): Node | null {
    const nodeType = this.getNodeType(type);
    if (!nodeType) return null;

    // Merge default data with override data
    const data = {
      ...nodeType.defaultData,
      ...overrideData,
      label: overrideData?.label || nodeType.label
    };

    return createNode(type, id, position, data);
  }
}

// Create singleton instance
const nodeRegistry = new NodeRegistry();

export default nodeRegistry; 