import React, { useEffect, useState } from "react";
import { Handle, Position, NodeProps } from "reactflow";
import { FolderPlus, Play, Tag } from "lucide-react";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Textarea } from "@/components/textarea";
import { Card, CardContent, CardHeader } from "@/components/card";
import { Separator } from "@/components/separator";
import { HandleTooltip } from "../../components/HandleTooltip";
import { TestDialog } from "../../components/TestDialog";
import { getNodeColors } from "../../utils/nodeColors";
import { ZendeskTicketNodeData } from "../../types/nodes";
import { zendeskTicketOutput } from "@/services/workflows";

const ZendeskTicketNode: React.FC<NodeProps<ZendeskTicketNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const colors = getNodeColors("zendeskTicketNode");

  const [name, setName] = useState(data.name);
  const [subject, setSubject] = useState(data.subject);
  const [description, setDescription] = useState(data.description);
  const [requesterName, setRequesterName] = useState(data.requester_name || "");
  const [requesterEmail, setRequesterEmail] = useState(
    data.requester_email || ""
  );
  const [tagsCsv, setTagsCsv] = useState((data.tags || []).join(","));

  const [isTestDialogOpen, setIsTestDialogOpen] = useState(false);
  const [testResponse, setTestResponse] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const tagsArr = tagsCsv
      .split(",")
      .map((t) => t.trim())
      .filter((t) => t.length > 0);
    if (data.updateNodeData) {
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

  const runTest = async () => {
    setIsLoading(true);
    setError(null);
    setTestResponse("");
    try {
      const res = await zendeskTicketOutput({
        subject,
        description,
        requester_name: requesterName,
        requester_email: requesterEmail,
        tags: tagsCsv
          .split(",")
          .map((t) => t.trim())
          .filter((t) => t),
      });
      setTestResponse(JSON.stringify(res, null, 2));
    } catch (e: any) {
      setError(e.message);
      setTestResponse(`Error: ${e.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <Card 
        className={`w-[420px] shadow-lg transition-all duration-200 ${
          selected 
            ? "shadow-xl" 
            : "shadow-md hover:shadow-lg"
        }`}
      >
        <CardHeader 
          className={`${colors.header} relative overflow-hidden`}
          style={{
            background: `linear-gradient(135deg, ${colors.header} 0%, ${colors.header}dd 100%)`
          }}
        >
          <div className="flex items-center justify-between relative z-10">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-white/20 rounded-lg backdrop-blur-sm">
                <Tag className="h-4 w-4 text-white" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">Zendesk Ticket</h3>
                <p className="text-xs text-white/80">Create support ticket</p>
              </div>
            </div>
            <Button
              size="sm"
              variant="ghost"
              className="h-8 w-8 text-white hover:bg-white/20 hover:text-white transition-colors"
              onClick={() => setIsTestDialogOpen(true)}
            >
              <Play className="h-4 w-4" />
            </Button>
          </div>
          
          <div className="absolute inset-0 opacity-10">
            <div className="absolute -right-4 -top-4 w-24 h-24 rounded-full bg-white/20"></div>
            <div className="absolute -left-2 -bottom-2 w-16 h-16 rounded-full bg-white/10"></div>
          </div>
        </CardHeader>

        <CardContent className="p-5 space-y-5">
          <div className="space-y-3">
            <div className="flex items-center space-x-2 text-sm font-medium text-muted-foreground">
              <div className="w-2 h-2 bg-primary rounded-full"></div>
              <span>Ticket Information</span>
            </div>
            
            <div className="space-y-3">
              <div className="space-y-2">
                <Label htmlFor="subject" className="text-sm font-medium">
                  Subject *
                </Label>
                <Input
                  id="subject"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  placeholder="Enter ticket subject..."
                  className="transition-all duration-200"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="description" className="text-sm font-medium">
                  Description *
                </Label>
                <Textarea
                  id="description"
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Describe the issue or request..."
                  className="transition-all duration-200 resize-none"
                />
              </div>
            </div>
          </div>

          <Separator className="my-3" />

          <div className="space-y-3">
            <div className="flex items-center space-x-2 text-sm font-medium text-muted-foreground">
              <div className="w-2 h-2 bg-secondary rounded-full"></div>
              <span>Requester Information</span>
              <span className="text-xs bg-muted px-2 py-1 rounded-full">Optional</span>
            </div>
            
            <div className="grid grid-cols-1 gap-3">
              <div className="space-y-2">
                <Label htmlFor="requester_name" className="text-sm font-medium">
                  Requester Name
                </Label>
                <Input
                  id="requester_name"
                  value={requesterName}
                  onChange={(e) => setRequesterName(e.target.value)}
                  placeholder="e.g., Alice Smith"
                  className="transition-all duration-200"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="requester_email" className="text-sm font-medium">
                  Requester Email
                </Label>
                <Input
                  id="requester_email"
                  type="email"
                  value={requesterEmail}
                  onChange={(e) => setRequesterEmail(e.target.value)}
                  placeholder="e.g., alice@example.com"
                  className="transition-all duration-200"
                />
              </div>
            </div>
          </div>

          <Separator className="my-3" />

          <div className="space-y-3">
            <div className="flex items-center space-x-2 text-sm font-medium text-muted-foreground">
              <div className="w-2 h-2 bg-accent rounded-full"></div>
              <span>Tags</span>
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="tags" className="text-sm font-medium">
                Tags (comma-separated)
              </Label>
              <Input
                id="tags"
                value={tagsCsv}
                onChange={(e) => setTagsCsv(e.target.value)}
                placeholder="e.g., support, urgent, follow-up"
                className="transition-all duration-200"
              />
              {tagsCsv && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {tagsCsv.split(",").map((tag, index) => {
                    const trimmedTag = tag.trim();
                    if (!trimmedTag) return null;
                    return (
                      <span
                        key={index}
                        className="inline-flex items-center px-2 py-1 text-xs font-medium bg-primary/10 text-primary rounded-full"
                      >
                        {trimmedTag}
                      </span>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </CardContent>

        {data.handlers
          ?.filter(h => h.type !== "source")
          .map(h => (
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
                border: "2px solid hsl(var(--background))",
                boxShadow: "0 2px 4px rgba(0,0,0,0.1)"
              }}
            />
          ))}

        {data.handlers
          ?.filter(h => h.type === "source")
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
                border: "2px solid hsl(var(--background))",
                boxShadow: "0 2px 4px rgba(0,0,0,0.1)"
              }}
            />
          ))}
      </Card>

      <TestDialog
        isOpen={isTestDialogOpen}
        onClose={() => setIsTestDialogOpen(false)}
        title={`Test Zendesk: ${name}`}
        inputFields={[]}
        onRun={runTest}
        output={testResponse}
        isLoading={isLoading}
        error={error}
      />
    </>
  );
};

export default ZendeskTicketNode;
