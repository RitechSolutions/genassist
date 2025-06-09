import React, { useEffect, useState } from "react";
import { Handle, Position, NodeProps } from "reactflow";
import { FolderPlus, Play } from "lucide-react";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Textarea } from "@/components/textarea";
import { HandleTooltip } from "../../components/HandleTooltip";
import { TestDialog } from "../../components/TestDialog";
import { getNodeColors } from "../../utils/nodeColors";

import { ZendeskTicketNodeData } from "../../types/nodes";
import { zendeskTicketOutput } from "@/services/workflows";

const ZendeskOutputNode: React.FC<NodeProps<ZendeskTicketNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const colors = getNodeColors("zendeskTicketNode");

  const [name, setName] = useState(data.name || "Zendesk Ticket");
  const [subject, setSubject] = useState(data.subject || "");
  const [description, setDescription] = useState(data.description || "");
  const [requesterName, setRequesterName] = useState(data.requester_name || "");
  const [requesterEmail, setRequesterEmail] = useState(data.requester_email || "");
  const [tagsCsv, setTagsCsv] = useState((data.tags || []).join(","));

  const [isTestDialogOpen, setIsTestDialogOpen] = useState(false);
  const [testResponse, setTestResponse] = useState<string>("");
  const [isLoadingTest, setIsLoadingTest] = useState(false);
  const [testError, setTestError] = useState<string | null>(null);

  useEffect(() => {
    if (data.updateNodeData) {
      const tagsArr = tagsCsv
        .split(",")
        .map((t) => t.trim())
        .filter((t) => t.length > 0);

    data.updateNodeData<ZendeskTicketNodeData>(id, {
      name,
      subject,
      description,
      requester_name: requesterName,
      requester_email: requesterEmail,
      tags: tagsArr,
    });

    }
  }, [name, subject, description, requesterName, requesterEmail, tagsCsv]);

  const executeZendeskTicket = async () => {
    setIsLoadingTest(true);
    setTestError(null);
    setTestResponse("");

    try {
      const result = await zendeskTicketOutput({
        subject,
        description,
        requester_name: requesterName,
        requester_email: requesterEmail,
        tags: tagsCsv
          .split(",")
          .map((t) => t.trim())
          .filter((t) => t.length > 0),
      });
      setTestResponse(JSON.stringify(result, null, 2));
    } catch (e: any) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      setTestError(msg);
      setTestResponse(`Error: ${msg}`);
    } finally {
      setIsLoadingTest(false);
    }
  };

  return (
    <>
      <div
        className={`border-2 rounded-md bg-white shadow-md w-[400px] ${
          selected ? "border-yellow-500" : "border-gray-200"
        }`}
      >
        <div
          className={`px-4 py-2 border-b ${colors.header} flex justify-between items-center`}
        >
          <div className="flex items-center">
            <FolderPlus className="h-4 w-4 text-white mr-2" />
            <div className="text-sm font-medium text-white">Zendesk Ticket</div>
          </div>
          <div className="flex space-x-1">
            <Button
              size="icon"
              variant="ghost"
              className="h-6 w-6 text-white hover:bg-yellow-500"
              title="Test Zendesk ticket"
              onClick={() => setIsTestDialogOpen(true)}
            >
              <Play className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>

        <div className="p-4 space-y-3">
          <div className="space-y-1">
            <Label htmlFor="subject">Subject</Label>
            <Input
              id="subject"
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Ticket subject"
            />
          </div>

          <div className="space-y-1">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Ticket description..."
            />
          </div>

          <div className="space-y-1">
            <Label htmlFor="requester_name">Requester Name (optional)</Label>
            <Input
              id="requester_name"
              type="text"
              value={requesterName}
              onChange={(e) => setRequesterName(e.target.value)}
              placeholder="Alice Smith"
            />
          </div>

          <div className="space-y-1">
            <Label htmlFor="requester_email">Requester Email (optional)</Label>
            <Input
              id="requester_email"
              type="email"
              value={requesterEmail}
              onChange={(e) => setRequesterEmail(e.target.value)}
              placeholder="alice@example.com"
            />
          </div>

          <div className="space-y-1">
            <Label htmlFor="tags">Tags (comma‑separated)</Label>
            <Input
              id="tags"
              type="text"
              value={tagsCsv}
              onChange={(e) => setTagsCsv(e.target.value)}
              placeholder="genassist, follow_up"
            />
          </div>
        </div>

        {data.handlers?.map((handler, idx) => (
          <HandleTooltip
            key={handler.id}
            type={handler.type}
            position={handler.type === "source" ? Position.Right : Position.Left}
            id={handler.id}
            nodeId={id}
            compatibility={handler.compatibility}
            style={{ top: `${(idx + 1) * (100 / data.handlers.length)}%`, backgroundColor: "orange" }}
            
          />
        ))}
      </div>

      <TestDialog
        isOpen={isTestDialogOpen}
        onClose={() => setIsTestDialogOpen(false)}
        title={`Test Zendesk Ticket: ${name}`}
        description="Create a test Zendesk ticket with these settings"
        inputFields={[]}  
        onRun={executeZendeskTicket}
        output={testResponse}
        isLoading={isLoadingTest}
        error={testError}
      />
    </>
  );
};

export default ZendeskOutputNode;
