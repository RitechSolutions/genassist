import { useMemo } from "react";
import { Node } from "reactflow";
import { useQuery } from "@tanstack/react-query";
import {
  X,
  CheckCircle2,
  Sparkles,
  ChevronRight,
  AlertCircle,
  Play,
} from "lucide-react";
import { getAllNodeSchemas } from "@/services/workflows";
import { getEmptyRequiredFields } from "../../utils/nodeValidation";
import nodeRegistry from "../../registry/nodeRegistry";

interface SetupStep {
  nodeId: string;
  nodeType: string;
  label: string;
  missingFields: string[];
  completed: boolean;
}

interface SetupWizardPanelProps {
  nodes: Node[];
  onNodeFocus: (nodeId: string) => void;
  onClose: () => void;
  onTest: () => void;
}

export const SetupWizardPanel = ({
  nodes,
  onNodeFocus,
  onClose,
  onTest,
}: SetupWizardPanelProps) => {
  // Fetch the same node schemas used by the node validation system
  const { data: nodeSchemas, isError: schemasError } = useQuery({
    queryKey: ["nodeSchemas"],
    queryFn: getAllNodeSchemas,
  });

  /** Build setup steps from canvas nodes using real schema validation + registry labels */
  const steps: SetupStep[] = useMemo(() => {
    if (!nodeSchemas) return [];

    const result: SetupStep[] = [];
    for (const node of nodes) {
      const nodeType = node.type ?? "";
      const schema = nodeSchemas[nodeType];
      if (!schema) continue;

      const data = (node.data ?? {}) as Record<string, unknown>;
      const missingFields = getEmptyRequiredFields(data, schema);

      // Only show nodes that have required fields defined in their schema
      const hasRequiredFields = schema.some((f) => f.required);
      if (!hasRequiredFields) continue;

      // Get label from the node registry (dynamic, no hardcoded map)
      const regDef = nodeRegistry.getNodeType(nodeType);
      const label = regDef?.label ?? nodeType.replace(/Node$/, "");

      result.push({
        nodeId: node.id,
        nodeType,
        label,
        missingFields,
        completed: missingFields.length === 0,
      });
    }
    return result;
  }, [nodes, nodeSchemas]);

  const completedCount = steps.filter((s) => s.completed).length;
  const allDone = steps.length > 0 && completedCount === steps.length;

  if (schemasError || steps.length === 0) return null;

  return (
    <div className="fixed bottom-20 left-4 z-30 w-80 animate-fade-up">
      <style>{`@keyframes scale-in { from { transform: scale(0); opacity: 0; } to { transform: scale(1); opacity: 1; } }`}</style>
      <div className="rounded-2xl border border-[#e2e8f0] bg-white shadow-xl shadow-black/5 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-[#5b4bff]/5 to-[#8b5cf6]/5 border-b border-[#e2e8f0]">
          <div className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-[#5b4bff] to-[#8b5cf6] flex items-center justify-center">
              <Sparkles className="h-3.5 w-3.5 text-white" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-[#0f172a]">
                Setup your workflow
              </h3>
              <p className="text-xs text-[#64748b]">
                {completedCount}/{steps.length} configured
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="h-6 w-6 rounded-md flex items-center justify-center text-[#94a3b8] hover:text-[#64748b] hover:bg-[#f1f5f9] transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Progress bar */}
        <div className="h-1 bg-[#f1f5f9]">
          <div
            className="h-full bg-gradient-to-r from-[#5b4bff] to-[#8b5cf6] transition-all duration-500"
            style={{
              width: `${steps.length > 0 ? (completedCount / steps.length) * 100 : 0}%`,
            }}
          />
        </div>

        {/* Steps */}
        <div className="p-2 space-y-1 max-h-80 overflow-y-auto">
          {steps.map((step) => (
            <button
              key={step.nodeId}
              onClick={() => onNodeFocus(step.nodeId)}
              className="w-full flex items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-all duration-150 hover:bg-[#f8fafc] group"
            >
              {/* Status icon with completion animation */}
              {step.completed ? (
                <span className="inline-flex shrink-0 animate-[scale-in_0.3s_ease-out]">
                  <CheckCircle2 className="h-5 w-5 text-[#16a34a]" />
                </span>
              ) : (
                <AlertCircle className="h-5 w-5 text-[#f59e0b] shrink-0" />
              )}

              {/* Text */}
              <div className="min-w-0 flex-1">
                <p
                  className={`text-sm font-medium ${
                    step.completed
                      ? "text-[#94a3b8] line-through"
                      : "text-[#334155]"
                  }`}
                >
                  {step.label}
                </p>
                <p className="text-xs text-[#94a3b8] truncate">
                  {step.completed
                    ? "All fields configured"
                    : `Missing: ${step.missingFields.join(", ")}`}
                </p>
              </div>

              {/* Arrow */}
              {!step.completed && (
                <ChevronRight className="h-4 w-4 text-[#cbd5e1] shrink-0 group-hover:text-[#5b4bff] transition-colors" />
              )}
            </button>
          ))}
        </div>

        {/* All done — prompt to test */}
        {allDone && (
          <div className="px-4 py-3 bg-[#f0fdf4] border-t border-[#dcfce7] space-y-2">
            <p className="text-sm font-medium text-[#16a34a] text-center">
              All integrations configured!
            </p>
            <button
              onClick={onTest}
              className="w-full flex items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-[#5b4bff] to-[#8b5cf6] px-4 py-2 text-sm font-medium text-white hover:opacity-90 transition-opacity"
            >
              <Play className="h-3.5 w-3.5" />
              Test your workflow
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

/** Small floating button to reopen the setup wizard after it's been closed */
export const SetupWizardReopenButton = ({ onClick }: { onClick: () => void }) => (
  <button
    onClick={onClick}
    className="fixed bottom-20 left-4 z-30 h-10 w-10 rounded-full bg-gradient-to-br from-[#5b4bff] to-[#8b5cf6] shadow-lg shadow-[#5b4bff]/20 flex items-center justify-center hover:opacity-90 transition-opacity"
    title="Reopen setup wizard"
  >
    <Sparkles className="h-4 w-4 text-white" />
  </button>
);
