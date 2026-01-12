import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Textarea } from "@/components/textarea";
import { Switch } from "@/components/switch";
import { Button } from "@/components/button";
import { toast } from "react-hot-toast";
import { X, Plus, Copy, Check, RefreshCw, AlertTriangle } from "lucide-react";
import {
  MCPServer,
  MCPServerCreatePayload,
  MCPServerUpdatePayload,
  MCPServerWorkflow,
} from "@/interfaces/mcp-server.interface";
import { createMCPServer, updateMCPServer } from "@/services/mcpServer";
import { getAllWorkflows } from "@/services/workflows";
import { Workflow } from "@/interfaces/workflow.interface";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { ScrollArea } from "@/components/scroll-area";

interface Props {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onServerSaved?: () => void;
  onServerUpdated?: (server: MCPServer) => void;
  mode?: "create" | "edit";
  serverToEdit?: MCPServer | null;
}

export function MCPServerDialog({
  isOpen,
  onOpenChange,
  onServerSaved,
  onServerUpdated,
  mode = "create",
  serverToEdit,
}: Props) {
  const [name, setName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [description, setDescription] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [selectedWorkflows, setSelectedWorkflows] = useState<MCPServerWorkflow[]>([]);
  const [isLoadingWorkflows, setIsLoadingWorkflows] = useState(false);
  const [isApiKeyGenerated, setIsApiKeyGenerated] = useState(false);
  const [isApiKeyCopied, setIsApiKeyCopied] = useState(false);

  useEffect(() => {
    if (isOpen) {
      const fetchWorkflows = async () => {
        setIsLoadingWorkflows(true);
        try {
          const workflowsData = await getAllWorkflows();
          setWorkflows(workflowsData);
        } catch (error) {
          toast.error("Failed to load workflows");
        } finally {
          setIsLoadingWorkflows(false);
        }
      };

      fetchWorkflows();

      if (mode === "edit" && serverToEdit) {
        setName(serverToEdit.name);
        setApiKey(""); // Don't show existing API key for security
        setDescription(serverToEdit.description || "");
        setIsActive(serverToEdit.is_active === 1);
        setSelectedWorkflows(serverToEdit.workflows || []);
        setIsApiKeyGenerated(false);
        setIsApiKeyCopied(false);
      } else {
        setName("");
        setApiKey("");
        setDescription("");
        setIsActive(true);
        setSelectedWorkflows([]);
        setIsApiKeyGenerated(false);
        setIsApiKeyCopied(false);
      }
    }
  }, [isOpen, mode, serverToEdit]);

  const generateApiKey = () => {
    // Generate a cryptographically secure random API key
    // Format: mcp_ followed by 32 random hex characters
    const array = new Uint8Array(16);
    crypto.getRandomValues(array);
    const hexString = Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('');
    const newApiKey = `mcp_${hexString}`;
    setApiKey(newApiKey);
    setIsApiKeyGenerated(true);
    setIsApiKeyCopied(false);
    // Auto-copy to clipboard
    copyApiKeyToClipboard(newApiKey);
  };

  const copyApiKeyToClipboard = async (keyToCopy?: string) => {
    const key = keyToCopy || apiKey;
    if (!key) return;
    
    try {
      await navigator.clipboard.writeText(key);
      setIsApiKeyCopied(true);
      toast.success("API key copied to clipboard");
      setTimeout(() => setIsApiKeyCopied(false), 3000);
    } catch (error) {
      toast.error("Failed to copy API key");
    }
  };

  const handleSubmit = async () => {
    const missingFields: string[] = [];
    if (!name.trim()) missingFields.push("Name");
    if (mode === "create" && !apiKey.trim()) missingFields.push("API Key");
    if (selectedWorkflows.length === 0) missingFields.push("At least one workflow");

    if (missingFields.length > 0) {
      if (missingFields.length === 1) {
        toast.error(`${missingFields[0]} is required.`);
      } else {
        toast.error(`Please provide: ${missingFields.join(", ")}.`);
      }
      return;
    }

    // Validate all workflows have tool names and descriptions
    const invalidWorkflows = selectedWorkflows.filter(
      (w) => !w.tool_name.trim() || !w.tool_description.trim()
    );
    if (invalidWorkflows.length > 0) {
      toast.error("All workflows must have a tool name and description.");
      return;
    }

    setIsSubmitting(true);
    try {
      const payload: MCPServerCreatePayload | MCPServerUpdatePayload = {
        name,
        description: description || undefined,
        is_active: isActive ? 1 : 0,
        workflows: selectedWorkflows,
      };

      if (mode === "create") {
        (payload as MCPServerCreatePayload).api_key = apiKey;
        await createMCPServer(payload as MCPServerCreatePayload);
        toast.success("MCP server created successfully.");
        // Reset API key state after saving
        setIsApiKeyGenerated(false);
        setIsApiKeyCopied(false);
        onServerSaved?.();
        onOpenChange(false);
      } else if (serverToEdit) {
        // Only update API key if provided
        if (apiKey.trim()) {
          (payload as MCPServerUpdatePayload).api_key = apiKey;
        }
        await updateMCPServer(serverToEdit.id, payload as MCPServerUpdatePayload);
        toast.success("MCP server updated successfully.");

        if (onServerUpdated) {
          const updatedServer: MCPServer = {
            ...serverToEdit,
            ...payload,
            workflows: selectedWorkflows,
          };
          onServerUpdated(updatedServer);
        }

        onOpenChange(false);
      }
    } catch (error: unknown) {
      const errorMessage =
        error && typeof error === "object" && "status" in error && error.status === 400
          ? ": A server with this name already exists"
          : "";
      toast.error(`Failed to ${mode} MCP server${errorMessage}.`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const addWorkflow = (workflowId: string) => {
    const workflow = workflows.find((w) => w.id === workflowId);
    if (!workflow) return;

    // Check if already added
    if (selectedWorkflows.some((w) => w.workflow_id === workflowId)) {
      toast.error("Workflow already added");
      return;
    }

    setSelectedWorkflows([
      ...selectedWorkflows,
      {
        workflow_id: workflowId,
        tool_name: workflow.name.toLowerCase().replace(/\s+/g, "_"),
        tool_description: workflow.description || `Execute ${workflow.name} workflow`,
      },
    ]);
  };

  const removeWorkflow = (workflowId: string) => {
    setSelectedWorkflows(selectedWorkflows.filter((w) => w.workflow_id !== workflowId));
  };

  const updateWorkflowToolName = (workflowId: string, toolName: string) => {
    setSelectedWorkflows(
      selectedWorkflows.map((w) =>
        w.workflow_id === workflowId ? { ...w, tool_name: toolName } : w
      )
    );
  };

  const updateWorkflowToolDescription = (
    workflowId: string,
    toolDescription: string
  ) => {
    setSelectedWorkflows(
      selectedWorkflows.map((w) =>
        w.workflow_id === workflowId
          ? { ...w, tool_description: toolDescription }
          : w
      )
    );
  };

  const availableWorkflows = workflows.filter(
    (w) => !selectedWorkflows.some((sw) => sw.workflow_id === w.id)
  );

  const handleDialogClose = (open: boolean) => {
    if (!open && isApiKeyGenerated && !isApiKeyCopied && apiKey) {
      // Warn user if they're closing without copying
      const confirmed = window.confirm(
        "You haven't copied the API key yet. This key can only be viewed once. Are you sure you want to close without copying it?"
      );
      if (!confirmed) {
        return;
      }
    }
    // Reset states when closing
    if (!open) {
      setIsApiKeyGenerated(false);
      setIsApiKeyCopied(false);
    }
    onOpenChange(open);
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleDialogClose}>
      <DialogContent className="sm:max-w-[700px] p-0 flex flex-col max-h-[90vh]">
        <DialogHeader className="p-6 pb-4 flex-shrink-0">
          <DialogTitle>
            {mode === "create" ? "Add New MCP Server" : "Edit MCP Server"}
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-6">
          <div className="grid gap-4 pb-4">
            <div>
              <Label htmlFor="name">Name *</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="My MCP Server"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <Label htmlFor="api-key">
                  API Key {mode === "create" ? "*" : "(leave blank to keep existing)"}
                </Label>
                {mode === "create" && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={generateApiKey}
                    className="h-7 text-xs"
                  >
                    <RefreshCw className="h-3 w-3 mr-1" />
                    Generate
                  </Button>
                )}
              </div>
              
              {isApiKeyGenerated && (
                <div className="mb-3 p-3 bg-yellow-50 border border-yellow-200 rounded-md">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="h-4 w-4 text-yellow-600 mt-0.5 flex-shrink-0" />
                    <div className="flex-1">
                      <p className="text-xs font-medium text-yellow-800 mb-1">
                        Important: Copy this API key now
                      </p>
                      <p className="text-xs text-yellow-700">
                        This API key can only be viewed once. Make sure to copy and save it securely before continuing.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              <div className="flex items-center gap-2">
                <Input
                  id="api-key"
                  type={isApiKeyGenerated ? "text" : "password"}
                  value={apiKey}
                  onChange={(e) => {
                    setApiKey(e.target.value);
                    setIsApiKeyGenerated(false);
                    setIsApiKeyCopied(false);
                  }}
                  placeholder={mode === "edit" ? "Enter new API key or leave blank" : "Click Generate or enter API key"}
                  className={isApiKeyGenerated ? "font-mono text-sm" : ""}
                  readOnly={isApiKeyGenerated}
                />
                {apiKey && (
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    className="h-10 w-10 flex-shrink-0"
                    onClick={() => copyApiKeyToClipboard()}
                    title="Copy API key"
                  >
                    {isApiKeyCopied ? (
                      <Check className="h-4 w-4 text-green-600" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </Button>
                )}
              </div>
              <p className="text-xs text-gray-500 mt-1">
                {isApiKeyGenerated
                  ? "API key generated. Copy it now - you won't be able to see it again after saving."
                  : "API key for authenticating MCP client requests"}
              </p>
            </div>

            <div>
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                placeholder="Optional description for this MCP server"
              />
            </div>

            <div>
              <Label>Workflows *</Label>
              <p className="text-xs text-gray-500 mb-3">
                Select workflows to expose as MCP tools. Each workflow will be available as a tool with a custom name and description.
              </p>

              {selectedWorkflows.length === 0 && availableWorkflows.length === 0 ? (
                <div className="text-sm text-gray-500 text-center py-8 border-2 border-dashed rounded-md bg-gray-50">
                  <p className="mb-1">No workflows available</p>
                  <p className="text-xs">Create workflows first to expose them as MCP tools</p>
                </div>
              ) : (
                <div className="space-y-3 max-h-[400px] overflow-y-auto pr-2">
                  {selectedWorkflows.map((sw) => {
                    const workflow = workflows.find((w) => w.id === sw.workflow_id);
                    return (
                      <div
                        key={sw.workflow_id}
                        className="border rounded-lg p-4 space-y-3 bg-white shadow-sm"
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1 min-w-0">
                            <p className="font-medium text-sm truncate">
                              {workflow?.name || "Unknown Workflow"}
                            </p>
                            {workflow?.description && (
                              <p className="text-xs text-gray-500 mt-1 line-clamp-1">
                                {workflow.description}
                              </p>
                            )}
                          </div>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 flex-shrink-0 ml-2"
                            onClick={() => removeWorkflow(sw.workflow_id)}
                            title="Remove workflow"
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        </div>

                        <div className="grid grid-cols-1 gap-3">
                          <div>
                            <Label htmlFor={`tool-name-${sw.workflow_id}`} className="text-xs font-medium">
                              Tool Name *
                            </Label>
                            <Input
                              id={`tool-name-${sw.workflow_id}`}
                              value={sw.tool_name}
                              onChange={(e) =>
                                updateWorkflowToolName(sw.workflow_id, e.target.value)
                              }
                              placeholder="e.g., execute_my_workflow"
                              className="text-sm mt-1"
                            />
                            <p className="text-xs text-gray-500 mt-1">
                              Name to expose this workflow as in MCP (use lowercase with underscores)
                            </p>
                          </div>

                          <div>
                            <Label htmlFor={`tool-desc-${sw.workflow_id}`} className="text-xs font-medium">
                              Tool Description *
                            </Label>
                            <Textarea
                              id={`tool-desc-${sw.workflow_id}`}
                              value={sw.tool_description}
                              onChange={(e) =>
                                updateWorkflowToolDescription(
                                  sw.workflow_id,
                                  e.target.value
                                )
                              }
                              placeholder="Description of what this tool does"
                              rows={2}
                              className="text-sm mt-1"
                            />
                            <p className="text-xs text-gray-500 mt-1">
                              Description that will be shown to MCP clients
                            </p>
                          </div>
                        </div>
                      </div>
                    );
                  })}

                  {availableWorkflows.length > 0 && (
                    <div className="relative">
                      <Select
                        onValueChange={addWorkflow}
                        disabled={isLoadingWorkflows}
                      >
                        <SelectTrigger className="w-full border-2 border-dashed rounded-lg p-4 hover:border-primary hover:bg-primary/5 transition-colors h-auto">
                          <div className="flex items-center justify-center gap-2 text-sm text-gray-600">
                            <Plus className="h-4 w-4" />
                            <span>Add Workflow</span>
                          </div>
                        </SelectTrigger>
                        <SelectContent>
                          {availableWorkflows.map((workflow) => (
                            <SelectItem key={workflow.id} value={workflow.id || ""}>
                              {workflow.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="flex items-center space-x-2 pt-2">
              <Switch
                id="is-active"
                checked={isActive}
                onCheckedChange={setIsActive}
              />
              <Label htmlFor="is-active">Active</Label>
            </div>
          </div>
        </div>

        <DialogFooter className="px-6 py-4 border-t flex-shrink-0">
          <div className="flex justify-end gap-3 w-full">
            <Button
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={isSubmitting}>
              {isSubmitting
                ? "Saving..."
                : mode === "create"
                ? "Create MCP Server"
                : "Update MCP Server"}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

