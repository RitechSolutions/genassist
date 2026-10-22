import { Node } from "reactflow";
import { getAgentConfigsList, getAllKnowledgeItems } from "@/services/api";
import { getAllAppSettings } from "@/services/appSettings";
import { getAudioProvidersMinimal } from "@/services/audioProviders";
import { hasPermission } from "@/services/auth";
import { getAllDataSources } from "@/services/dataSources";
import { getFallbackChainsMinimal } from "@/services/fallbackChains";
import { getLLMProvidersMinimal } from "@/services/llmProviders";
import { getAllMLModels } from "@/services/mlModels";
import { getAllWorkflows, getWorkflowsMinimal } from "@/services/workflows";
import { KnowledgeItem } from "@/interfaces/knowledge.interface";
import { Workflow, WorkflowMinimal } from "@/interfaces/workflow.interface";
import {
  MissingReference,
  ReferenceKind,
  ReferenceTarget,
  findMissingReferences,
  getReferencedKinds,
} from "./workflowReferences";

const AGENT_PAGE_SIZE = 100;

// Version names repeat across agents, so lead with the agent.
const workflowLabel = ({
  name,
  version,
  agent_name,
  is_active_version,
}: Pick<WorkflowMinimal, "name" | "version" | "agent_name" | "is_active_version">) => {
  const marks = [`v${version}`, ...(is_active_version ? ["active"] : [])].join(", ");
  return `${agent_name ? `${agent_name} · ` : ""}${name} (${marks})`;
};

// Same lookup as the Workflow Executor dialog
const inputNames = (workflow: Workflow): string[] | undefined => {
  const schema = workflow.nodes?.find((node) => node.type?.includes("InputNode"))?.data
    ?.inputSchema;
  return schema && typeof schema === "object" ? Object.keys(schema) : undefined;
};

// The Workflow Executor picker's list. The minimal one only adds agent names.
const loadWorkflows = async (): Promise<ReferenceTarget[] | null> => {
  const [workflows, minimal] = await Promise.all([
    getAllWorkflows(),
    getWorkflowsMinimal().catch(() => null),
  ]);
  const named = new Map<string, WorkflowMinimal>(
    minimal?.map((workflow) => [workflow.id, workflow])
  );
  return (
    workflows?.flatMap((workflow) =>
      workflow.id
        ? [
            {
              id: workflow.id,
              name: workflow.name,
              label: workflowLabel(named.get(workflow.id) ?? workflow),
              isActive: true,
              inputs: inputNames(workflow),
            },
          ]
        : []
    ) ?? null
  );
};

const loadAgents = async (): Promise<ReferenceTarget[] | null> => {
  const targets: ReferenceTarget[] = [];
  for (let page = 1; ; page++) {
    const result = await getAgentConfigsList(page, AGENT_PAGE_SIZE);
    if (!result) return null;
    for (const agent of result.items) {
      targets.push({ id: agent.id, name: agent.name, label: agent.name, isActive: agent.is_active });
    }
    if (result.items.length < AGENT_PAGE_SIZE || targets.length >= result.total) return targets;
  }
};

// null when the list can't be read here, e.g. without permission.
const LOADERS: Record<ReferenceKind, () => Promise<ReferenceTarget[] | null>> = {
  llmProvider: async () =>
    (await getLLMProvidersMinimal())?.map((provider) => ({
      id: provider.id,
      name: provider.name,
      label: `${provider.name} (${provider.llm_model_provider} - ${provider.llm_model})`,
      isActive: provider.is_active === 1,
    })) ?? null,
  fallbackChain: async () =>
    (await getFallbackChainsMinimal())?.map((chain) => ({
      id: chain.id,
      name: chain.name,
      label: chain.name,
      isActive: chain.is_active === 1,
    })) ?? null,
  knowledgeBase: async () =>
    ((await getAllKnowledgeItems()) as KnowledgeItem[] | null)?.map((base) => ({
      id: base.id,
      name: base.name,
      label: base.name,
      isActive: true,
    })) ?? null,
  // These two services answer [] when the list can't be read.
  appSetting: async () =>
    hasPermission("read:app_settings")
      ? (await getAllAppSettings()).map((setting) => ({
          id: setting.id,
          name: setting.name,
          label: setting.name,
          isActive: setting.is_active === 1,
          type: setting.type,
        }))
      : null,
  mlModel: async () =>
    hasPermission("read:ml_model")
      ? (await getAllMLModels()).map((model) => {
          const baseline = model.inference_params?.ratioBaselineColumn;
          return {
            id: model.id,
            name: model.name,
            label: model.name,
            isActive: true,
            // What the node's own picker asks values for
            inputs: [...(model.features ?? []), ...(baseline ? [baseline] : [])],
          };
        })
      : null,
  dataSource: async () =>
    (await getAllDataSources())?.flatMap((source) =>
      source.id
        ? [
            {
              id: source.id,
              name: source.name,
              label: `${source.name} (${source.source_type})`,
              isActive: source.is_active === 1,
              type: source.source_type,
            },
          ]
        : []
    ) ?? null,
  workflow: loadWorkflows,
  agent: loadAgents,
  audioProvider: async () =>
    (await getAudioProvidersMinimal())?.map((provider) => ({
      id: provider.id,
      name: provider.name,
      label: provider.name,
      isActive: provider.is_active === 1,
      type: provider.capability,
      provider: provider.provider_type,
    })) ?? null,
};

export interface ReferenceCheck {
  missing: MissingReference[];
  targets: Partial<Record<ReferenceKind, ReferenceTarget[]>>;
}

// Lists what the nodes refer to here and finds the ids that aren't there.
export const checkReferences = async (
  nodes: Node[],
  skipKinds: ReferenceKind[] = []
): Promise<ReferenceCheck> => {
  const kinds = getReferencedKinds(nodes).filter((kind) => !skipKinds.includes(kind));
  const lists = await Promise.all(kinds.map((kind) => LOADERS[kind]().catch(() => null)));
  const targets: ReferenceCheck["targets"] = {};
  const known: Partial<Record<ReferenceKind, Set<string>>> = {};
  kinds.forEach((kind, i) => {
    const list = lists[i];
    if (!list) return;
    targets[kind] = list;
    known[kind] = new Set(list.map((target) => target.id));
  });
  return { missing: findMissingReferences(nodes, known), targets };
};
