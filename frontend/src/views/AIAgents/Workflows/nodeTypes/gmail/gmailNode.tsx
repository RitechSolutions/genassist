import React, { useEffect, useState } from "react";
import { Position, NodeProps } from "reactflow";
import { Card } from "@/components/card";
import { HandleTooltip } from "../../components/HandleTooltip";
import { TestDialog } from "../../components/TestDialog";
import { getNodeColors } from "../../utils/nodeColors";
import { GmailNodeData } from "../../types/nodes";
import { gmailOutput } from "@/services/workflows";
import { getAllDataSources } from "@/services/dataSources";
import { DataSource } from "@/interfaces/dataSource.interface";
import { useQuery } from "@tanstack/react-query";
import NodeHeader from "../nodeHeader";
import NodeContent from "../nodeContent";
import { GmailDialog } from "../../components/GmailDialog";

const GmailNode: React.FC<NodeProps<GmailNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const colors = getNodeColors("gmailNode");

  const [isTestDialogOpen, setIsTestDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [testResponse, setTestResponse] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: connectors = [] } = useQuery({
    queryKey: ["dataSources"],
    queryFn: getAllDataSources,
    select: (data: DataSource[]) =>
      data.filter((p) => p.is_active === 1 && p.source_type === "gmail"),
  });

  useEffect(() => {
    if (data.dataSourceId === undefined && connectors.length > 0) {
      if (data.updateNodeData) {
        data.updateNodeData<GmailNodeData>(id, {
          ...data,
          dataSourceId: connectors[0].id,
        });
      }
    }
  }, [connectors, data.dataSourceId, id, data]);

  const runTest = async () => {
    setIsLoading(true);
    setError(null);
    setTestResponse("");
    try {
      const res = await gmailOutput({
        subject: data.subject,
        body: data.body,
        to: data.to,
        cc: data.cc,
        bcc: data.bcc,
        attachments: data.attachments,
        dataSourceId: data.dataSourceId,
      });
      setTestResponse(JSON.stringify(res, null, 2));
    } catch (e: any) {
      setError(e.message);
      setTestResponse(`Error: ${e.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const onUpdate = (updatedData: Partial<GmailNodeData>) => {
    if (data.updateNodeData) {
      data.updateNodeData(id, { ...data, ...updatedData });
    }
  };

  const selectedConnectorName =
    connectors.find((c) => c.id === data.dataSourceId)?.name || "Not Selected";

  return (
    <>
      <Card
        className={`w-[420px] shadow-lg transition-all duration-200 ${
          selected
            ? "shadow-xl border-blue-500"
            : "shadow-md border-transparent"
        }`}
      >
        <NodeHeader
          iconName={"mail"}
          title={data.name || "Gmail Output"}
          subtitle={"Compose and send an email"}
          color={colors.header}
          onTest={() => setIsTestDialogOpen(true)}
          onSettings={() => setIsEditDialogOpen(true)}
        />

        <NodeContent
          data={[
            { label: "To", value: data.to },
            { label: "CC", value: data.cc },
            { label: "BCC", value: data.bcc },
            { label: "Subject", value: data.subject },
            { label: "Message Body", value: data.body },
            {
              label: "File Attachments",
              value: data.attachments.map((a) => a.name).join(", "),
            },
          ]}
        />

        {data.handlers
          ?.filter((h) => h.type !== "source")
          .map((h) => (
            <HandleTooltip
              key={h.id}
              type={h.type}
              position={Position.Left}
              id={h.id}
              nodeId={id}
              compatibility={h.compatibility}
              style={{
                top: "50%",
                transform: "translateY(-50%)",
                backgroundColor: "hsl(var(--primary))",
              }}
            />
          ))}

        {data.handlers
          ?.filter((h) => h.type === "source")
          .map((h, i, arr) => (
            <HandleTooltip
              key={h.id}
              type={h.type}
              position={Position.Right}
              id={h.id}
              nodeId={id}
              compatibility={h.compatibility}
              style={{
                top: `${(i + 1) * (100 / (arr.length + 1))}%`,
                backgroundColor: "hsl(var(--secondary))",
              }}
            />
          ))}
      </Card>

      <GmailDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        connectors={connectors}
      />

      <TestDialog
        isOpen={isTestDialogOpen}
        onClose={() => setIsTestDialogOpen(false)}
        title={`Test Gmail: ${data.name || "Gmail Output"}`}
        inputFields={[]}
        onRun={runTest}
        output={testResponse}
        isLoading={isLoading}
        error={error}
      />
    </>
  );
};

export default GmailNode;
