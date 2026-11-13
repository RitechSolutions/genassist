import React from "react";
import { NodeProps } from "reactflow";
import { useQuery } from "@tanstack/react-query";
import { WorkflowBuilderToolsNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import { NodeContentRow } from "../nodeContent";
import nodeRegistry from "../../registry/nodeRegistry";
import { getBuilderTools } from "@/services/workflowBuilder";

export const WORKFLOW_BUILDER_TOOLS_NODE_TYPE = "workflowBuilderToolsNode";

const plural = (count: number) => `${count} tool${count === 1 ? "" : "s"}`;

/**
 * Gives the connected agent the Workflow Builder tool set (search nodes, read
 * and edit the workflow draft, finalize). The tools themselves are defined on
 * the backend; this node has nothing to configure, so its body just describes
 * what the agent gets.
 */
const WorkflowBuilderToolsNode: React.FC<
  NodeProps<WorkflowBuilderToolsNodeData>
> = ({ id, data, selected }) => {
  const nodeDefinition = nodeRegistry.getNodeType(
    WORKFLOW_BUILDER_TOOLS_NODE_TYPE
  );
  const color = getNodeColor(nodeDefinition?.category || "ai");

  // The tool set is fixed per backend build, so one fetch per page is enough.
  const { data: allTools, isError } = useQuery({
    queryKey: ["workflowBuilderTools"],
    queryFn: getBuilderTools,
    staleTime: Infinity,
  });

  // An empty selection means every tool (same rule as the backend node).
  const enabled = data.enabledTools?.length ? new Set(data.enabledTools) : null;
  const exposed = allTools?.filter((t) => !enabled || enabled.has(t.name));
  const toolsSummary = !exposed
    ? isError
      ? "Unavailable (backend has no tools endpoint yet)"
      : ""
    : enabled && allTools
      ? `${exposed.length} of ${plural(allTools.length)}`
      : plural(exposed.length);

  const nodeContent: NodeContentRow[] = [
    {
      label: "Description",
      value: data.description || nodeDefinition?.description,
    },
    { label: "Tools", value: toolsSummary, placeholder: "Loading tools…" },
    {
      label: "Includes",
      value: exposed?.map((t) => t.name).join(", ") ?? "",
      placeholder: "",
    },
  ];

  return (
    <BaseNodeContainer
      id={id}
      data={data}
      selected={selected}
      iconName={nodeDefinition?.icon || "FolderGit2"}
      title={data.name || nodeDefinition?.label || "Workflow Builder Tools"}
      subtitle={
        nodeDefinition?.shortDescription || "Tools for building workflows"
      }
      color={color}
      nodeType={WORKFLOW_BUILDER_TOOLS_NODE_TYPE}
      nodeContent={nodeContent}
    />
  );
};

export default React.memo(WorkflowBuilderToolsNode);
