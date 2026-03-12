import { useMemo } from "react";
import { ArrowDown, Sparkles } from "lucide-react";
import type { OnboardingMessage } from "@/views/Onboarding/hooks/useOnboardingChat";
import type { WorkflowDraft } from "@/views/Onboarding/utils/extractWorkflowDraft";
import nodeRegistry from "@/views/AIAgents/Workflows/registry/nodeRegistry";

interface DetectedNode {
  key: string;
  label: string;
}

/** Build search terms from the node registry dynamically. */
const buildRegistryIndex = () => {
  const entries: { key: string; label: string; terms: RegExp[] }[] = [];

  for (const def of nodeRegistry.getAllNodeTypes()) {
    if (def.category === "formatting" || def.category === "training") continue;

    const rawTerms = new Set<string>();

    const typeName = def.type.replace(/Node$/, "");
    typeName.split(/(?=[A-Z])/).forEach((w) => {
      const lower = w.toLowerCase();
      if (lower.length >= 3) rawTerms.add(lower);
    });

    def.label.split(/\s+/).forEach((w) => {
      const lower = w.toLowerCase();
      if (lower.length >= 3) rawTerms.add(lower);
    });

    const terms = Array.from(rawTerms).map(
      (t) => new RegExp(`\\b${t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`, "i")
    );

    entries.push({ key: def.type, label: def.label, terms });
  }

  return entries;
};

let _registryIndex: ReturnType<typeof buildRegistryIndex> | null = null;
const getRegistryIndex = () => {
  if (!_registryIndex) _registryIndex = buildRegistryIndex();
  return _registryIndex;
};

/** Map a WorkflowDraft to display nodes using the registry for labels */
const draftToNodes = (draft: WorkflowDraft): DetectedNode[] => {
  return draft.workflow.map((node) => {
    const regDef = nodeRegistry.getNodeType(node.node_name);
    return {
      key: node.uniqueId,
      label: regDef?.label ?? node.function_of_node,
    };
  });
};

/** Detect nodes from the LATEST agent message only, so the preview
 *  reflects the current state rather than accumulating over time. */
const detectNodesFromMessages = (
  messages: OnboardingMessage[]
): DetectedNode[] => {
  // Find the last agent message
  const lastAgentMsg = [...messages].reverse().find((m) => m.role === "agent");
  if (!lastAgentMsg) return [];

  const text = lastAgentMsg.text;
  if (!text) return [];

  const index = getRegistryIndex();
  const detected: DetectedNode[] = [];
  const seen = new Set<string>();

  for (const entry of index) {
    if (seen.has(entry.key)) continue;
    if (entry.terms.some((p) => p.test(text))) {
      seen.add(entry.key);
      detected.push({ key: entry.key, label: entry.label });
    }
  }

  return detected;
};

interface WorkflowPreviewProps {
  messages: OnboardingMessage[];
  workflowDraft: WorkflowDraft | null;
}

export const WorkflowPreview = ({
  messages,
  workflowDraft,
}: WorkflowPreviewProps) => {
  const nodes = useMemo(() => {
    if (workflowDraft) return draftToNodes(workflowDraft);
    return detectNodesFromMessages(messages);
  }, [messages, workflowDraft]);

  if (nodes.length === 0) return null;

  return (
    <div className="w-full max-w-xs mx-auto animate-fade-up">
      <div className="rounded-2xl border border-[#e2e8f0] bg-white/80 backdrop-blur-sm shadow-sm p-4">
        <div className="flex items-center gap-2 mb-3">
          <Sparkles className="h-3.5 w-3.5 text-[#5b4bff]" />
          <span className="text-xs font-semibold text-[#64748b] uppercase tracking-wider">
            {workflowDraft ? "Your workflow" : "Building..."}
          </span>
        </div>

        <div className="space-y-0">
          {nodes.map((node, index) => (
            <div key={node.key}>
              <div
                className="flex items-center gap-2.5 rounded-xl border border-[#e2e8f0] bg-white px-3 py-2 shadow-sm animate-fade-up"
                style={{ animationDelay: `${index * 100}ms` }}
              >
                <div className="h-7 w-7 shrink-0 rounded-lg bg-[#f1f5f9] flex items-center justify-center text-[#5b4bff]">
                  <Sparkles className="h-3.5 w-3.5" />
                </div>
                <span className="text-xs font-medium text-[#334155] truncate">
                  {node.label}
                </span>
              </div>

              {index < nodes.length - 1 && (
                <div className="flex justify-center py-0.5">
                  <ArrowDown className="h-3.5 w-3.5 text-[#cbd5e1]" />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
