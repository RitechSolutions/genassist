import { Node } from "reactflow";
import { getNodeDisplayName } from "./nodeDeletion";

// Objects a node points at by id. Each environment has its own rows.
export type ReferenceKind =
  | "llmProvider"
  | "fallbackChain"
  | "knowledgeBase"
  | "appSetting"
  | "dataSource"
  | "mlModel"
  | "workflow"
  | "agent"
  | "audioProvider";

// Also the order the dialog lists missing references in.
export const REFERENCE_KIND_NOUNS: Record<ReferenceKind, string> = {
  llmProvider: "LLM provider",
  fallbackChain: "fallback chain",
  knowledgeBase: "knowledge base",
  appSetting: "configuration var",
  dataSource: "data source",
  mlModel: "ML model",
  workflow: "workflow",
  agent: "agent",
  audioProvider: "audio provider",
};

export interface ReferenceTarget {
  id: string;
  name: string;
  label: string;
  isActive: boolean;
  // App setting type, data source type or audio capability
  type?: string;
  provider?: string;
  // Inputs the node keeps values for: a workflow's input names or a model's features
  inputs?: string[];
}

export interface ReferenceField {
  key: string;
  label: string;
  kind: ReferenceKind;
  multiple?: boolean;
  // Data key that keeps a copy of the target's name
  nameKey?: string;
  // Same filter as the node's own picker
  accepts?: (target: ReferenceTarget) => boolean;
  // Other data the node's own picker changes along with the target
  onReplace?: (data: Record<string, unknown>, target: ReferenceTarget) => void;
}

const isActive = (target: ReferenceTarget) => target.isActive;

const typeIncludes = (types: string[]) => (target: ReferenceTarget) =>
  types.some((type) => target.type?.toLowerCase().includes(type));

const llmProvider: ReferenceField = {
  key: "providerId",
  label: "LLM provider",
  kind: "llmProvider",
  accepts: isActive,
};

const llmFields: ReferenceField[] = [
  llmProvider,
  { key: "fallbackChainId", label: "Fallback chain", kind: "fallbackChain", accepts: isActive },
  { key: "compactingModel", label: "Compacting model", kind: "llmProvider", accepts: isActive },
];

const appSetting = (type: string): ReferenceField => ({
  key: "app_settings_id",
  label: "Configuration vars",
  kind: "appSetting",
  accepts: (target) => target.isActive && target.type?.toLowerCase() === type,
});

const gmailConnection: ReferenceField = {
  key: "dataSourceId",
  label: "Data source",
  kind: "dataSource",
  accepts: (target) => target.isActive && target.type === "gmail",
};

const audioProvider = (capability: string): ReferenceField => ({
  key: "audioProviderId",
  label: "Audio provider",
  kind: "audioProvider",
  accepts: (target) => target.type === capability || target.type === "both",
});

// Keeps only the new target's inputs under `key`, as the node's own picker does.
const matchInputs =
  (key: string) => (data: Record<string, unknown>, target: ReferenceTarget) => {
    if (!target.inputs) return;
    const values = data[key];
    const old = new Map(Object.entries(values && typeof values === "object" ? values : {}));
    data[key] = Object.fromEntries(target.inputs.map((name) => [name, old.get(name) || ""]));
  };

export const REFERENCE_FIELDS: Record<string, ReferenceField[]> = {
  llmModelNode: llmFields,
  agentNode: llmFields,
  subAgentNode: llmFields,
  voiceAgentNode: [
    {
      key: "voiceProviderId",
      label: "Audio provider",
      kind: "audioProvider",
      accepts: (target) => target.provider === "gemini",
    },
  ],
  knowledgeBaseNode: [
    { key: "selectedBases", label: "Knowledge bases", kind: "knowledgeBase", multiple: true },
  ],
  routerNode: [llmProvider],
  switchNode: [llmProvider],
  nlpNode: [llmProvider],
  openApiNode: [llmProvider],
  sqlNode: [
    {
      key: "dataSourceId",
      label: "Data source",
      kind: "dataSource",
      accepts: typeIncludes(["sql", "database", "mysql", "postgres", "sqlite", "snowflake"]),
    },
    llmProvider,
  ],
  guardrailProvenanceNode: [{ ...llmProvider, key: "llm_provider_id" }],
  slackMessageNode: [appSetting("slack")],
  whatsappToolNode: [appSetting("whatsapp")],
  zendeskTicketNode: [appSetting("zendesk")],
  jiraNode: [appSetting("jira")],
  salesforceCaseNode: [appSetting("salesforce")],
  gmailNode: [gmailConnection],
  readMailsNode: [gmailConnection],
  calendarEventNode: [
    {
      key: "dataSourceId",
      label: "Data source",
      kind: "dataSource",
      accepts: (target) => (target.isActive && target.type === "gmail") || target.type === "o365",
    },
  ],
  trainDataSourceNode: [
    {
      key: "dataSourceId",
      label: "Data source",
      kind: "dataSource",
      accepts: (target) => ["snowflake", "database"].includes(target.type?.toLowerCase() ?? ""),
    },
  ],
  mlModelInferenceNode: [
    {
      key: "modelId",
      label: "ML model",
      kind: "mlModel",
      nameKey: "modelName",
      onReplace: matchInputs("inferenceInputs"),
    },
  ],
  workflowExecutorNode: [
    {
      key: "workflowId",
      label: "Workflow",
      kind: "workflow",
      nameKey: "workflowName",
      onReplace: matchInputs("inputParameters"),
    },
  ],
  createWorkflowScheduleNode: [{ key: "agentId", label: "Agent", kind: "agent" }],
  ttsNode: [audioProvider("tts")],
  sttNode: [audioProvider("stt")],
};

export interface ReferencePlace {
  nodeId: string;
  nodeName: string;
  field: ReferenceField;
}

// Ids that aren't in this environment, with every place that uses them.
// A list field misses all its unknown ids at once, so they stay together.
export interface MissingReference {
  kind: ReferenceKind;
  ids: string[];
  multiple: boolean;
  // Name the node kept for it, if it keeps one
  name?: string;
  places: ReferencePlace[];
}

export interface ReferenceReplacement {
  nodeId: string;
  field: ReferenceField;
  from: string[];
  to: ReferenceTarget[];
}

const nodeData = (node: Node): Record<string, unknown> =>
  (node.data ?? {}) as Record<string, unknown>;

const fieldIds = (data: Record<string, unknown>, field: ReferenceField): string[] => {
  const value = data[field.key];
  const values = field.multiple ? (Array.isArray(value) ? value : []) : [value];
  // A {{variable}} is filled in at run time, so it isn't an id.
  const ids = values.filter(
    (v): v is string => typeof v === "string" && v.trim() !== "" && !v.includes("{{")
  );
  return [...new Set(ids)];
};

export const getReferencedKinds = (nodes: Node[]): ReferenceKind[] => {
  const kinds = new Set<ReferenceKind>();
  for (const node of nodes) {
    for (const field of REFERENCE_FIELDS[node.type ?? ""] ?? []) {
      if (fieldIds(nodeData(node), field).length > 0) kinds.add(field.kind);
    }
  }
  return [...kinds];
};

// Kinds missing from `known` couldn't be listed here, so their ids are not checked.
export const findMissingReferences = (
  nodes: Node[],
  known: Partial<Record<ReferenceKind, ReadonlySet<string>>>
): MissingReference[] => {
  const missing = new Map<string, MissingReference>();
  for (const node of nodes) {
    const data = nodeData(node);
    for (const field of REFERENCE_FIELDS[node.type ?? ""] ?? []) {
      const knownIds = known[field.kind];
      if (!knownIds) continue;
      const ids = fieldIds(data, field).filter((id) => !knownIds.has(id));
      if (ids.length === 0) continue;
      const multiple = !!field.multiple;
      const key = `${field.kind}:${multiple ? "list:" : ""}${[...ids].sort().join(",")}`;
      const entry = missing.get(key) ?? { kind: field.kind, ids, multiple, places: [] };
      const keptName = field.nameKey ? data[field.nameKey] : undefined;
      if (!entry.name && typeof keptName === "string" && keptName) entry.name = keptName;
      entry.places.push({ nodeId: node.id, nodeName: getNodeDisplayName(node), field });
      missing.set(key, entry);
    }
  }
  const order = Object.keys(REFERENCE_KIND_NOUNS);
  return [...missing.values()].sort((a, b) => order.indexOf(a.kind) - order.indexOf(b.kind));
};

// Targets every one of `fields` would offer.
export const acceptedTargets = (
  targets: ReferenceTarget[],
  fields: ReferenceField[]
): ReferenceTarget[] =>
  targets.filter((target) => fields.every((field) => field.accepts?.(target) ?? true));

export const replaceReferences = (
  nodes: Node[],
  replacements: ReferenceReplacement[]
): Node[] => {
  if (replacements.length === 0) return nodes;
  return nodes.map((node) => {
    const own = replacements.filter((replacement) => replacement.nodeId === node.id);
    if (own.length === 0) return node;
    const data = { ...nodeData(node) };
    for (const { field, from, to } of own) {
      const value = data[field.key];
      if (field.multiple && Array.isArray(value)) {
        const kept = value.filter((v) => !from.includes(v));
        data[field.key] = [...new Set([...kept, ...to.map((target) => target.id)])];
      } else if (from.includes(value as string) && to[0]) {
        data[field.key] = to[0].id;
        if (field.nameKey) data[field.nameKey] = to[0].name;
        field.onReplace?.(data, to[0]);
      }
    }
    return { ...node, data };
  });
};
