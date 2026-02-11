import { Workflow } from "@/interfaces/workflow.interface";
import { Node, ReactFlowInstance } from "reactflow";
import { v4 as uuidv4 } from "uuid";
import nodeRegistry from "../registry/nodeRegistry";
import { NodeData } from "../types/nodes";
import { NodeSchema, SchemaType } from "../types/schemas";

export const getHandlerPosition = (index: number, total: number) => {
  return `${(index + 1) * (100 / (total + 1))}%`;
};

// Calculate next version based on existing workflows
export const calculateNextVersion = (workflows: Workflow[]): string => {
  if (workflows.length === 0) {
    return "1.0";
  }

  // Extract and parse version numbers
  const versions = workflows
    .map((workflow) => {
      const version = workflow.version;
      if (!version) return 0;

      // Parse version
      const parsed = parseFloat(version);
      return isNaN(parsed) ? 0 : parsed;
    })
    .filter((version) => version > 0);

  if (versions.length === 0) {
    return "1.0";
  }

  // Find the highest version and add 0.1
  const maxVersion = Math.max(...versions);
  const nextVersion = maxVersion + 0.1;

  // Format to one decimal place
  return nextVersion.toFixed(1);
};

// Check if a version already exists in the workflows
export const isVersionDuplicate = (
  workflows: Workflow[],
  version: string,
  excludeWorkflowId?: string
): boolean => {
  if (!version?.trim()) return false;

  return workflows.some(
    (workflow) =>
      workflow.version?.trim() === version.trim() &&
      workflow.id !== excludeWorkflowId
  );
};

// Find the previous version to switch to when deleting a workflow
export const findPreviousVersion = (
  workflows: Workflow[],
  deletedWorkflow: Workflow
): Workflow | null => {
  if (workflows.length <= 1) return null;

  const remaining = workflows.filter((w) => w.id !== deletedWorkflow.id);
  if (!remaining.length) return null;

  const deletedVersion = parseFloat(deletedWorkflow.version || "0");

  const versioned = remaining
    .map((w) => ({
      ...w,
      parsedVersion: parseFloat(w.version || "0"),
    }))
    .filter((w) => !isNaN(w.parsedVersion) && w.parsedVersion > 0);

  // If no valid versions exist, fallback to the most recently created workflow
  if (!versioned.length) {
    return getMostRecentWorkflow(remaining);
  }
  // Find all workflows with a version lower than the one being deleted
  const previous = versioned.filter((w) => w.parsedVersion < deletedVersion);
  if (previous.length) {
    return getHighestVersion(previous);
  }

  const next = versioned.filter((w) => w.parsedVersion > deletedVersion);
  if (next.length) {
    return getLowestVersion(next);
  }

  return getMostRecentWorkflow(remaining);
};

const getMostRecentWorkflow = (workflows: Workflow[]): Workflow =>
  workflows.reduce((latest, curr) =>
    new Date(curr.created_at) > new Date(latest.created_at) ? curr : latest
  );

const getHighestVersion = (
  workflows: (Workflow & { parsedVersion: number })[]
): Workflow =>
  workflows.reduce((max, curr) =>
    curr.parsedVersion > max.parsedVersion ? curr : max
  );

const getLowestVersion = (
  workflows: (Workflow & { parsedVersion: number })[]
): Workflow =>
  workflows.reduce((min, curr) =>
    curr.parsedVersion < min.parsedVersion ? curr : min
  );

export const maskToken = (token: string) => {
  if (!token) return "";
  const maskedLength = Math.min(token.length, 20); // Limit to 20 characters
  return "●".repeat(maskedLength) + (token.length > 20 ? "..." : "");
};

export const createWorkflowNodeFromDrop = (
  nodeType: string,
  position?: { x: number; y: number }
): Node | null => {
  const id = uuidv4();
  const nodePosition = position ?? { x: 0, y: 0 };

  const newNode = nodeRegistry.createNode(nodeType, id, nodePosition);
  return newNode;
};

export const getNodeDimensions = (
  node: Node
): { width: number; height: number } => {
  // Default fallback values
  let nodeWidth = 400;
  let nodeHeight = 200;

  // Get dimensions from the node's width/height
  if (node.width && node.height) {
    nodeWidth = node.width;
    nodeHeight = node.height;
  }

  return { width: nodeWidth, height: nodeHeight };
};

export const getNodeCenter = (
  position: { x: number; y: number },
  dimensions: { width: number; height: number }
): { x: number; y: number } => {
  const x = position.x + dimensions.width / 2;
  const y = position.y + dimensions.height / 2;

  return { x, y };
};

export const handleDragOver = (event: React.DragEvent) => {
  event.preventDefault();
  event.dataTransfer.dropEffect = "move";
};

export const handleDrop = (
  event: React.DragEvent,
  reactFlowInstance: ReactFlowInstance | null,
  restoreNodeFunctions: (nodes: Node[]) => Node[],
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>
): Node | null => {
  event.preventDefault();
  const nodeType = event.dataTransfer.getData("application/reactflow");

  if (typeof nodeType === "undefined" || !nodeType) {
    return null;
  }

  if (!reactFlowInstance) {
    return null;
  }

  // Convert screen coordinates to flow coordinates
  const position = reactFlowInstance.screenToFlowPosition({
    x: event.clientX,
    y: event.clientY,
  });

  const newNode = createWorkflowNodeFromDrop(nodeType, position);
  if (newNode) {
    const nodesWithFunctions = restoreNodeFunctions([newNode]);
    setNodes((nds) => nds.concat(nodesWithFunctions));
    return newNode;
  }

  return null;
};

export const handleNodeDoubleClick = (
  event: React.MouseEvent,
  node: Node,
  reactFlowInstance: ReactFlowInstance | null
): void => {
  if (!reactFlowInstance) return;

  const fullNode = reactFlowInstance.getNode(node.id);
  if (!fullNode || !fullNode.position) return;

  const dimensions = getNodeDimensions(fullNode);

  const center = getNodeCenter(fullNode.position, dimensions);

  reactFlowInstance.setCenter(center.x, center.y, {
    zoom: 1.5,
    duration: 800,
  });
};

/**
 * Extracts dynamic variables from a text string
 * @param text The text to extract variables from
 * @returns Set of variable names (without @ or {{}} prefix/suffix)
 */
export const extractDynamicVariables = (text: string): Set<string> => {
  const variables = new Set<string>();

  // Match @variable format
  // const atMatches = text.match(/@\w+/g) || [];
  // atMatches.forEach((v) => variables.add(v.slice(1)));

  // Match {{variable}} format (without spaces inside braces)
  const curlyMatches = text.match(/{{([^\s{}]+)}}/g) || [];
  curlyMatches.forEach((v) => variables.add(v.slice(2, -2)));

  return variables;
};
export const extractDynamicVariablesAsRecord = (
  text: string
): Record<string, { type: string; required?: boolean }> => {
  const variables = extractDynamicVariables(text);

  const params = Object.fromEntries(
    Array.from(variables).map((v) => [v, { type: "string", required: true }])
  );

  return params;
};

export const convertSchemaToParams = (
  schema: Record<string, { type: string; required?: boolean }>
) => {
  if (!schema) return {};
  return Object.entries(schema).reduce((acc, [key, value]) => {
    acc[key] = {
      type: value.type,
      required: value.required || false,
    };
    return acc;
  }, {} as Record<string, { type: string; required?: boolean }>);
};

/**
 * Generates sample output data for a node based on its inputSchema and extractedVariables
 * @param data The node data containing inputSchema and potentially other properties
 * @returns An object with generated values for each inputSchema field and extracted variable
 */
export const generateSampleOutput = (
  data: NodeData
): Record<string, unknown> => {
  const output: Record<string, unknown> = {};

  // Generate sample values for inputSchema fields
  if ("inputSchema" in data && data.inputSchema) {
    Object.entries(data.inputSchema).forEach(([fieldName, fieldSchema]) => {
      output[fieldName] = generateSampleValue(fieldSchema);
    });
  }

  // Generate sample values for extracted variables from text fields
  if ("template" in data && data.template) {
    const extractedVars = extractDynamicVariables(data.template);
    extractedVars.forEach((variable) => {
      if (!output[variable]) {
        output[variable] = generateSampleValue({ type: "string" });
      }
    });
  }

  // Check other text fields that might contain variables
  const textFields = [
    "message",
    "body",
    "subject",
    "description",
    "query",
    "code",
    "pythonScript",
  ];
  textFields.forEach((field) => {
    if (hasStringField(data, field)) {
      const textValue = getStringField(data, field);
      if (textValue) {
        const extractedVars = extractDynamicVariables(textValue);
        extractedVars.forEach((variable) => {
          if (!output[variable]) {
            output[variable] = generateSampleValue({ type: "string" });
          }
        });
      }
    }
  });

  return output;
};

export const generateTemplateFromInputSchema = (
  inputSchema: NodeSchema
): string => {
  if (inputSchema === null || inputSchema === undefined) {
    return "{}";
  }
  
  const entries = Object.entries(inputSchema);
  if (entries.length === 0) {
    return "{}";
  }
  
  // Build JSON string manually, checking types to determine if values should be quoted
  const parts = entries.map(([key, fieldSchema]) => {
    const templateValue = `{{direct_input.parameters.${key}}}`;
    const sourceKey = `source.${key}`;
    
    // Only quote string types; leave object, array, number, boolean unquoted
    const shouldQuote = fieldSchema.type === "string";
    
    // Use JSON.stringify for keys to properly escape special characters
    const escapedKey = JSON.stringify(sourceKey);
    
    if (shouldQuote) {
      // For string types, quote the template value
      return `${escapedKey}:${JSON.stringify(templateValue)}`;
    } else {
      // For non-string types, don't quote the template value
      return `${escapedKey}:${templateValue}`;
    }
  });
  
  return `{${parts.join(",")}}`;
};

/**
 * Generates a sample value based on a schema field definition
 * @param fieldSchema The schema field definition
 * @returns A sample value of the appropriate type
 */
const generateSampleValue = (fieldSchema: {
  type: string;
  properties?: Record<string, unknown>;
  items?: unknown;
}): unknown => {
  switch (fieldSchema.type) {
    case "string":
      return `sample_${fieldSchema.type}_value`;
    case "number":
      return 42;
    case "boolean":
      return true;
    case "array":
      if (fieldSchema.items) {
        return [
          generateSampleValue(
            fieldSchema.items as {
              type: string;
              properties?: Record<string, unknown>;
              items?: unknown;
            }
          ),
        ];
      }
      return ["sample_array_item"];
    case "object":
      if (fieldSchema.properties) {
        const obj: Record<string, unknown> = {};
        Object.entries(fieldSchema.properties).forEach(([key, prop]) => {
          obj[key] = generateSampleValue(
            prop as {
              type: string;
              properties?: Record<string, unknown>;
              items?: unknown;
            }
          );
        });
        return obj;
      }
      return { sample_key: "sample_value" };
    case "any":
      return "sample_any_value";
    default:
      return "sample_value";
  }
};

/**
 * Type guard to check if data has a specific field
 */
const hasStringField = (data: NodeData, field: string): boolean => {
  return (
    field in data &&
    typeof (data as unknown as Record<string, unknown>)[field] === "string"
  );
};

/**
 * Safely get a string field from data
 */
const getStringField = (data: NodeData, field: string): string | null => {
  if (hasStringField(data, field)) {
    return (data as unknown as Record<string, unknown>)[field] as string;
  }
  return null;
};

export const getValueFromPath = (
  obj: Record<string, unknown> | null | undefined,
  path: string
): unknown => {
  if (!obj || !path) return undefined;

  const keys = path.split(".");
  let current: unknown = obj;

  for (const key of keys) {
    if (
      current &&
      typeof current === "object" &&
      current !== null &&
      key in current
    ) {
      current = (current as Record<string, unknown>)[key];
    } else {
      return undefined;
    }
  }

  return current;
};

/**
 * Parses an input string value based on the schema field type
 * @param value The string value to parse
 * @param type The expected schema type
 * @returns Parsed value of the correct type, or the original string if parsing fails
 */
export const parseInputValue = (value: string, type: SchemaType): unknown => {
  if (!value || value.trim() === "") {
    return value;
  }

  try {
    switch (type) {
      case "string":
        return value;
      case "number": {
        const num = parseFloat(value);
        if (isNaN(num)) {
          throw new Error(`Invalid number: ${value}`);
        }
        return num;
      }
      case "boolean": {
        const lowerValue = value.toLowerCase().trim();
        if (lowerValue === "true" || lowerValue === "1" || lowerValue === "yes") {
          return true;
        }
        if (lowerValue === "false" || lowerValue === "0" || lowerValue === "no") {
          return false;
        }
        throw new Error(`Invalid boolean: ${value}`);
      }
      case "object":
      case "array":
        try {
          return JSON.parse(value);
        } catch (e) {
          throw new Error(`Invalid JSON: ${value}`);
        }
      case "any":
        // Try to parse as JSON first, then number, then boolean, finally string
        try {
          return JSON.parse(value);
        } catch {
          const num = parseFloat(value);
          if (!isNaN(num)) return num;
          const lowerValue = value.toLowerCase().trim();
          if (lowerValue === "true") return true;
          if (lowerValue === "false") return false;
          return value;
        }
      default:
        return value;
    }
  } catch (error) {
    // Return the original string if parsing fails
    console.warn(`Failed to parse value "${value}" as ${type}:`, error);
    return value;
  }
};

/**
 * Converts a value to a string representation for input fields
 * @param value The value to convert
 * @param type The schema type
 * @returns String representation of the value
 */
export const valueToString = (value: unknown, type: SchemaType): string => {
  if (value === null || value === undefined) {
    return "";
  }
  
  if (type === "object" || type === "array") {
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  }
  
  if (type === "boolean") {
    return String(value);
  }
  
  return String(value);
};

/**
 * Recursively truncates arrays to a maximum number of items.
 * Objects are traversed recursively; primitives are left as-is.
 */
export const truncateNodeOutput = (data: unknown, maxItems: number = 4): unknown => {
  if (Array.isArray(data)) {
    return data.slice(0, maxItems).map((item) => truncateNodeOutput(item, maxItems));
  }
  if (data !== null && typeof data === "object") {
    const result: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(data as Record<string, unknown>)) {
      result[key] = truncateNodeOutput(value, maxItems);
    }
    return result;
  }
  return data;
};