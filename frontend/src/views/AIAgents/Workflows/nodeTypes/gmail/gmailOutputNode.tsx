import React, { useEffect, useState } from "react";
import { Handle, Position, NodeProps } from "reactflow";
import { Mail, Play } from "lucide-react";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Textarea } from "@/components/textarea";
import { HandleTooltip } from "../../components/HandleTooltip";
import { TestDialog } from "../../components/TestDialog";
import { getNodeColors } from "../../utils/nodeColors";

import { GmailNodeData } from "../../types/nodes";
import { gmailOutput } from "@/services/workflows";

const GmailOutputNode: React.FC<NodeProps<GmailNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const colors = getNodeColors("gmailNode");

  const [name, setName] = useState(data.name || "Gmail");
  const [subject, setSubject] = useState(data.subject || "");
  const [body, setBody] = useState(data.body || "");
  const [to, setTo] = useState(data.to || "");
  const [cc, setCc] = useState(data.cc || "");
  const [bcc, setBcc] = useState(data.bcc || "");
  const [attachments, setAttachments] = useState(data.attachments || []);

  const [isTestDialogOpen, setIsTestDialogOpen] = useState(false);
  const [testResponse, setTestResponse] = useState<string>("");
  const [isLoadingTest, setIsLoadingTest] = useState(false);
  const [testError, setTestError] = useState<string | null>(null);

  useEffect(() => {
    if (data.updateNodeData) {
      data.updateNodeData<GmailNodeData>(id, {
        name,
        subject,
        body,
        to,
        cc,
        bcc,
        attachments,
      });
    }
  }, [name, subject, body, to, cc, bcc, attachments, id, data]);

  const executeGmail = async () => {
    setIsLoadingTest(true);
    setTestError(null);
    setTestResponse("");

    try {
      const result = await gmailOutput({
        subject,
        body,
        to,
        cc,
        bcc,
        attachments,
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
            <Mail className="h-4 w-4 text-white mr-2" />
            <div className="text-sm font-medium text-white">Gmail Output</div>
          </div>
          <div className="flex space-x-1">
            <Button
              size="icon"
              variant="ghost"
              className="h-6 w-6 text-white hover:bg-blue-500"
              title="Test Gmail output"
              onClick={() => setIsTestDialogOpen(true)}
            >
              <Play className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>

        <div className="p-4 space-y-3">
          <div className="space-y-1">
            <Label htmlFor="to">To (Recipients)</Label>
            <Input
              id="to"
              type="email"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              placeholder="recipient@example.com, another@example.com"
            />
          </div>

          <div className="space-y-1">
            <Label htmlFor="cc">CC (optional)</Label>
            <Input
              id="cc"
              type="email"
              value={cc}
              onChange={(e) => setCc(e.target.value)}
              placeholder="cc@example.com"
            />
          </div>

          <div className="space-y-1">
            <Label htmlFor="bcc">BCC (optional)</Label>
            <Input
              id="bcc"
              type="email"
              value={bcc}
              onChange={(e) => setBcc(e.target.value)}
              placeholder="bcc@example.com"
            />
          </div>

          <div className="space-y-1">
            <Label htmlFor="subject">Subject</Label>
            <Input
              id="subject"
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Email subject"
            />
          </div>

          <div className="space-y-1">
            <Label htmlFor="body">Message Body</Label>
            <Textarea
              id="body"
              rows={4}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Email message content..."
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
            style={{ 
              top: `${(idx + 1) * (100 / (data.handlers.length + 1))}%`
            }}
          />
        ))}
      </div>

      <TestDialog
        isOpen={isTestDialogOpen}
        onClose={() => setIsTestDialogOpen(false)}
        title={`Test Gmail Output: ${name}`}
        description="Send a test email with these settings"
        inputFields={[]}  
        onRun={executeGmail}
        output={testResponse}
        isLoading={isLoadingTest}
        error={testError}
      />
    </>
  );
};

export default GmailOutputNode;