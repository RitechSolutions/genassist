import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/dialog";
import { Button } from "@/components/button";
import { Label } from "@/components/label";
import { Badge } from "@/components/badge";
import { Copy, Check } from "lucide-react";
import { MCPServer } from "@/interfaces/mcp-server.interface";
import { getMCPServer } from "@/services/mcpServer";
import { toast } from "react-hot-toast";
import { formatDate } from "@/helpers/utils";

interface Props {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  serverId: string | null;
  onEdit?: (server: MCPServer) => void;
}

export function MCPServerDetailsDialog({
  isOpen,
  onOpenChange,
  serverId,
  onEdit,
}: Props) {
  const [server, setServer] = useState<MCPServer | null>(null);
  const [loading, setLoading] = useState(false);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && serverId) {
      fetchServerDetails();
    } else {
      setServer(null);
      setCopiedField(null);
    }
  }, [isOpen, serverId]);

  const fetchServerDetails = async () => {
    if (!serverId) return;
    setLoading(true);
    try {
      const data = await getMCPServer(serverId);
      setServer(data);
    } catch (error) {
      toast.error("Failed to load MCP server details");
      onOpenChange(false);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = async (text: string, fieldName: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedField(fieldName);
      toast.success("Copied to clipboard");
      setTimeout(() => setCopiedField(null), 2000);
    } catch (error) {
      toast.error("Failed to copy to clipboard");
    }
  };

  if (loading) {
    return (
      <Dialog open={isOpen} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>Loading...</DialogTitle>
          </DialogHeader>
          <div className="py-8 text-center text-gray-500">Loading server details...</div>
        </DialogContent>
      </Dialog>
    );
  }

  if (!server) {
    return null;
  }

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>MCP Server Details</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div>
            <Label className="text-xs text-gray-500">Name</Label>
            <p className="text-sm font-medium mt-1">{server.name}</p>
          </div>

          {server.description && (
            <div>
              <Label className="text-xs text-gray-500">Description</Label>
              <p className="text-sm mt-1">{server.description}</p>
            </div>
          )}

          <div>
            <Label className="text-xs text-gray-500">Status</Label>
            <div className="mt-1">
              <Badge variant={server.is_active === 1 ? "default" : "secondary"}>
                {server.is_active === 1 ? "Active" : "Inactive"}
              </Badge>
            </div>
          </div>

          {server.url && (
            <div>
              <Label className="text-xs text-gray-500">MCP Server URL</Label>
              <div className="mt-1 flex items-center gap-2">
                <code className="flex-1 bg-gray-100 px-3 py-2 rounded text-sm font-mono break-all">
                  {server.url}
                </code>
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  className="h-9 w-9 flex-shrink-0"
                  onClick={() => copyToClipboard(server.url || "", "url")}
                  title="Copy URL"
                >
                  {copiedField === "url" ? (
                    <Check className="h-4 w-4 text-green-600" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Use this URL to connect MCP clients to this server
              </p>
            </div>
          )}



          <div>
            <Label className="text-xs text-gray-500">Workflows</Label>
            <div className="mt-2 space-y-2">
              {server.workflows.length === 0 ? (
                <p className="text-sm text-gray-500">No workflows configured</p>
              ) : (
                server.workflows.map((workflow, index) => (
                  <div
                    key={workflow.workflow_id}
                    className="border rounded-md p-3 bg-gray-50"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <p className="text-sm font-medium">{workflow.tool_name}</p>
                        <p className="text-xs text-gray-500 mt-1">
                          {workflow.tool_description}
                        </p>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 pt-2 border-t">
            <div>
              <Label className="text-xs text-gray-500">Created</Label>
              <p className="text-sm mt-1">{formatDate(server.created_at)}</p>
            </div>
            <div>
              <Label className="text-xs text-gray-500">Last Updated</Label>
              <p className="text-sm mt-1">{formatDate(server.updated_at)}</p>
            </div>
          </div>
        </div>

        <DialogFooter>
          <div className="flex justify-between w-full">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Close
            </Button>
            {onEdit && (
              <Button onClick={() => {
                onEdit(server);
                onOpenChange(false);
              }}>
                Edit
              </Button>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

