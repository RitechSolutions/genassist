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
      <div className="rounded-2xl border border-slate-200 bg-white shadow-xl shadow-black/5 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-ai-brand/5 to-ai-brand-light/5 border-b border-slate-200">
          <div className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-ai-brand to-ai-brand-light flex items-center justify-center">
              <Sparkles className="h-3.5 w-3.5 text-white" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-900">
                Setup your workflow
              </h3>
              <p className="text-xs text-slate-500">
                {completedCount}/{steps.length} configured
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="h-6 w-6 rounded-md flex items-center justify-center text-slate-400 hover:text-slate-500 hover:bg-slate-100 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Progress bar */}
        <div className="h-1 bg-slate-100">
          <div
            className="h-full bg-gradient-to-r from-ai-brand to-ai-brand-light transition-all duration-500"
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
              className="w-full flex items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-all duration-150 hover:bg-slate-50 group"
            >
              {/* Status icon with completion animation */}
              {step.completed ? (
                <span className="inline-flex shrink-0 animate-[scale-in_0.3s_ease-out]">
                  <CheckCircle2 className="h-5 w-5 text-green-600" />
                </span>
              ) : (
                <AlertCircle className="h-5 w-5 text-amber-500 shrink-0" />
              )}

              {/* Text */}
              <div className="min-w-0 flex-1">
                <p
                  className={`text-sm font-medium ${
                    step.completed
                      ? "text-slate-400 line-through"
                      : "text-slate-700"
                  }`}
                >
                  {step.label}
                </p>
                <p className="text-xs text-slate-400 truncate">
                  {step.completed
                    ? "All fields configured"
                    : `Missing: ${step.missingFields.join(", ")}`}
                </p>
              </div>

              {/* Arrow */}
              {!step.completed && (
                <ChevronRight className="h-4 w-4 text-slate-300 shrink-0 group-hover:text-ai-brand transition-colors" />
              )}
            </button>
          ))}
        </div>

        {/* All done — prompt to test */}
        {allDone && (
          <div className="px-4 py-3 bg-green-50 border-t border-green-100 space-y-2">
            <p className="text-sm font-medium text-green-600 text-center">
              All integrations configured!
            </p>
            <button
              onClick={onTest}
              className="w-full flex items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-ai-brand to-ai-brand-light px-4 py-2 text-sm font-medium text-white hover:opacity-90 transition-opacity"
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
    className="fixed bottom-20 left-4 z-30 h-10 w-10 rounded-full bg-gradient-to-br from-ai-brand to-ai-brand-light shadow-lg shadow-ai-brand/20 flex items-center justify-center hover:opacity-90 transition-opacity"
    title="Reopen setup wizard"
  >
    <Sparkles className="h-4 w-4 text-white" />
  </button>
);
