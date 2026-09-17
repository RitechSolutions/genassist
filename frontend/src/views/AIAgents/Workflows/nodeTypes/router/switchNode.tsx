import React, { useEffect, useState } from "react";
import { NodeProps, useReactFlow, useUpdateNodeInternals } from "reactflow";
import { SwitchNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import { SwitchDialog } from "../../nodeDialogs/SwitchDialog";
import nodeRegistry from "../../registry/nodeRegistry";
import { Label } from "@/components/label";
import { getLLMProvider } from "@/services/llmProviders";
import { isSwitchSmartMode, SWITCH_MATCH_MODE_LABELS } from "./switchCases";
import { needsSwitchFanOut, SWITCH_FAN_OUT_THRESHOLD } from "./switchHandleLayout";
import SwitchFanOutHandles from "./SwitchFanOutHandles";
import { edgesOnRemovedHandles } from "../../utils/handleEdges";

// The card lists as many rows as fit before the outputs fan out: the first
// cases plus Default; the rest are summarised as "+N more".
const MAX_LISTED_CASES = SWITCH_FAN_OUT_THRESHOLD - 1;

export const SWITCH_NODE_TYPE = "switchNode";

const SwitchNode: React.FC<NodeProps<SwitchNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(SWITCH_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [providerName, setProviderName] = useState("");
  const smart = isSwitchSmartMode(data.smartModeEnabled);
  const { getEdges, deleteElements } = useReactFlow();
  const updateNodeInternals = useUpdateNodeInternals();

  // Output handles are derived from the cases, so React Flow must re-measure
  // them whenever a case is added, removed or reordered.
  const handleIds = (data.handlers ?? []).map((h) => h.id).join("|");
  useEffect(() => {
    updateNodeInternals(id);
  }, [id, handleIds, updateNodeInternals]);

  useEffect(() => {
    if (smart && data.providerId) {
      getLLMProvider(data.providerId).then((provider) => {
        if (provider) {
          setProviderName(
            `${provider.name} (${provider.llm_model_provider} - ${provider.llm_model})`
          );
        }
      });
    }
  }, [smart, data.providerId]);

  const onUpdate = (updatedData: SwitchNodeData) => {
    // Drop edges that were attached to a case that no longer exists.
    const staleEdges = edgesOnRemovedHandles(
      getEdges(),
      id,
      data.handlers,
      updatedData.handlers
    );
    if (staleEdges.length > 0) {
      deleteElements({ edges: staleEdges.map((edge) => ({ id: edge.id })) });
    }

    if (data.updateNodeData) {
      data.updateNodeData(id, {
        ...data,
        ...updatedData,
      });
    }
  };

  const cases = data.cases ?? [];
  const handlers = data.handlers ?? [];
  const outputCount = handlers.filter((h) => h.type === "source").length;
  const fanOut = needsSwitchFanOut(outputCount);
  const listedCases = cases.slice(0, MAX_LISTED_CASES);
  const hiddenCaseCount = cases.length - listedCases.length;
  const matchMode = SWITCH_MATCH_MODE_LABELS[data.matchMode ?? "equal"];
  const matchSummary = `${matchMode} · ${
    data.caseSensitive ? "Case sensitive" : "Case insensitive"
  }`;

  return (
    <>
      <BaseNodeContainer
        id={id}
        data={data}
        selected={selected}
        iconName={nodeDefinition.icon}
        title={data.name || nodeDefinition.label}
        subtitle={nodeDefinition.shortDescription}
        color={color}
        nodeType={SWITCH_NODE_TYPE}
        onSettings={() => setIsEditDialogOpen(true)}
        renderHandles={
          fanOut
            ? (variant) => (
                <SwitchFanOutHandles
                  nodeId={id}
                  handlers={handlers}
                  shape={variant === "compact" ? "arc" : "bracket"}
                />
              )
            : undefined
        }
      >
        <div className="p-4 mx-0.5 mb-0.5 bg-card rounded-sm">
          <div className="space-y-4">
            {(smart
              ? [
                  { label: "MODE", value: "Smart (LLM)" },
                  { label: "LLM PROVIDER", value: providerName || "—" },
                  { label: "ROUTING PROMPT", value: data.smartPrompt },
                ]
              : [
                  { label: "VALUE", value: data.switchValue },
                  { label: "MATCH", value: matchSummary },
                ]
            ).map((row) => (
              <div key={row.label} className="space-y-0">
                <Label className="text-muted-foreground font-semibold">
                  {row.label}
                </Label>
                {row.value ? (
                  <div
                    className="text-sm text-accent-foreground truncate max-w-full"
                    title={row.value}
                  >
                    {row.value}
                  </div>
                ) : (
                  <div className="text-sm text-accent-foreground italic">
                    None provided
                  </div>
                )}
              </div>
            ))}

            <div className="space-y-0">
              <Label className="text-muted-foreground font-semibold">
                {`CASES (${cases.length})`}
              </Label>
              <ul className="mt-1 space-y-1">
                {listedCases.map((switchCase, index) => (
                  <li
                    key={switchCase.id}
                    className="flex items-center gap-2 text-sm min-w-0"
                  >
                    <span className="flex h-5 min-w-5 shrink-0 items-center justify-center rounded bg-muted px-1 text-xs font-medium text-muted-foreground">
                      {index + 1}
                    </span>
                    <span className="truncate text-accent-foreground">
                      {switchCase.label || `Case ${index + 1}`}
                    </span>
                    <span
                      className={`ml-auto shrink-0 max-w-[45%] truncate ${
                        switchCase.value
                          ? smart
                            ? "text-xs text-muted-foreground"
                            : "font-mono text-xs text-muted-foreground"
                          : "italic text-muted-foreground"
                      }`}
                      title={switchCase.value}
                    >
                      {switchCase.value || (smart ? "No description" : "No value")}
                    </span>
                  </li>
                ))}
                {hiddenCaseCount > 0 && (
                  <li className="flex items-center gap-2 text-sm min-w-0">
                    <span className="flex h-5 min-w-5 shrink-0 items-center justify-center rounded bg-muted px-1 text-xs font-medium text-muted-foreground">
                      +
                    </span>
                    <span className="truncate font-medium text-accent-foreground">
                      {hiddenCaseCount} more
                    </span>
                    <span className="ml-auto shrink-0 text-xs text-muted-foreground">
                      Hover to see all
                    </span>
                  </li>
                )}
                <li className="flex items-center gap-2 text-sm min-w-0">
                  <span className="flex h-5 min-w-5 shrink-0 items-center justify-center rounded border border-dashed border-muted-foreground/40 px-1 text-xs text-muted-foreground">
                    ∗
                  </span>
                  <span className="truncate text-accent-foreground">
                    Default
                  </span>
                  <span className="ml-auto shrink-0 italic text-muted-foreground">
                    {smart ? "None chosen" : "No match"}
                  </span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </BaseNodeContainer>

      <SwitchDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={SWITCH_NODE_TYPE}
      />
    </>
  );
};

export default React.memo(SwitchNode);
