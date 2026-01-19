import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/button";
import { Workflow } from "@/interfaces/workflow.interface";
import { getAllWorkflows } from "@/services/workflows";
import { Mail, Headset, MessageSquare, MessageCircle, Calendar, ExternalLink, Clock, Sparkles } from "lucide-react";
import { format } from "date-fns";

interface Integration {
  id: string;
  name: string;
  description: string;
  icon: "mail" | "headset" | "slack" | "whatsapp" | "calendar";
  iconColor: string;
  bgColor: string;
}

interface IntegrationWorkflowsDialogProps {
  integration: Integration | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// Map integration icons to their corresponding workflow node types
const getNodeTypesForIntegration = (iconType: Integration["icon"]): string[] => {
  switch (iconType) {
    case "mail":
      return ["gmailNode", "readMailsNode"];
    case "headset":
      return ["zendeskTicketNode"];
    case "slack":
      return ["slackMessageNode"];
    case "whatsapp":
      return ["whatsappToolNode"];
    case "calendar":
      return ["calendarEventNode"];
    default:
      return [];
  }
};

const getIcon = (iconType: Integration["icon"], className: string = "w-5 h-5") => {
  const iconProps = { className };
  
  switch (iconType) {
    case "mail":
      return <Mail {...iconProps} />;
    case "headset":
      return <Headset {...iconProps} />;
    case "slack":
      return <MessageSquare {...iconProps} />;
    case "whatsapp":
      return <MessageCircle {...iconProps} />;
    case "calendar":
      return <Calendar {...iconProps} />;
    default:
      return <Mail {...iconProps} />;
  }
};

interface WorkflowWithUsageCount extends Workflow {
  usageCount: number;
}

export function IntegrationWorkflowsDialog({
  integration,
  open,
  onOpenChange,
}: IntegrationWorkflowsDialogProps) {
  const navigate = useNavigate();
  const [workflows, setWorkflows] = useState<WorkflowWithUsageCount[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !integration) {
      return;
    }

    const fetchWorkflows = async () => {
      setLoading(true);
      setError(null);
      
      try {
        const allWorkflows = await getAllWorkflows();
        const nodeTypes = getNodeTypesForIntegration(integration.icon);
        
        // Filter workflows that contain the integration node types
        const filteredWorkflows = allWorkflows
          .map((workflow) => {
            const nodes = workflow.nodes || [];
            const usageCount = nodes.filter((node) =>
              nodeTypes.includes(node.type || "")
            ).length;
            
            return {
              ...workflow,
              usageCount,
            };
          })
          .filter((workflow) => workflow.usageCount > 0);
        
        setWorkflows(filteredWorkflows);
      } catch (err) {
        console.error("Error fetching workflows:", err);
        setError("Failed to load workflows. Please try again.");
      } finally {
        setLoading(false);
      }
    };

    fetchWorkflows();
  }, [open, integration]);

  const handleWorkflowClick = (workflow: Workflow) => {
    // Navigate to the workflow editor
    if (workflow.agent_id && workflow.id) {
      navigate(`/aiagents/${workflow.agent_id}/workflows?workflow=${workflow.id}`);
      onOpenChange(false);
    }
  };

  const handleCreateWorkflow = () => {
    navigate("/aiagents");
    onOpenChange(false);
  };

  if (!integration) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className={`${integration.bgColor} flex items-center p-3 rounded-lg`}>
              <div className={integration.iconColor}>
                {getIcon(integration.icon, "w-6 h-6")}
              </div>
            </div>
            <div>
              <DialogTitle className="text-xl">
                {integration.name} Workflows
              </DialogTitle>
              <DialogDescription className="mt-1">
                {workflows.length === 0 && !loading
                  ? "No workflows using this integration"
                  : `${workflows.length} workflow${workflows.length !== 1 ? "s" : ""} using this integration`}
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto mt-4">
          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="h-24 bg-gray-100 rounded-lg animate-pulse"
                />
              ))}
            </div>
          ) : error ? (
            <div className="text-center py-8">
              <p className="text-red-600 mb-4">{error}</p>
              <Button
                onClick={() => onOpenChange(false)}
                variant="secondary"
              >
                Close
              </Button>
            </div>
          ) : workflows.length === 0 ? (
            <div className="text-center py-12">
              <div className="mb-4 flex justify-center">
                <div className="bg-gray-100 p-4 rounded-full">
                  {getIcon(integration.icon, "w-8 h-8 text-gray-400")}
                </div>
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                No workflows yet
              </h3>
              <p className="text-gray-600 mb-6 max-w-sm mx-auto">
                Create your first workflow using {integration.name} to automate
                your processes.
              </p>
              <Button
                onClick={handleCreateWorkflow}
              >
                <Sparkles className="w-4 h-4" />
                Create Workflow
              </Button>
            </div>
          ) : (
            <div className="border border-border rounded-xl overflow-hidden">
              {workflows.map((workflow, index) => (
                <div
                  key={workflow.id}
                  onClick={() => handleWorkflowClick(workflow)}
                  className={`px-4 py-3.5 hover:bg-muted/50 transition-colors cursor-pointer group ${
                    index !== workflows.length - 1 ? "border-b border-border" : ""
                  }`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h4 className="text-base font-medium text-foreground truncate group-hover:text-foreground transition-colors">
                          {workflow.name}
                        </h4>
                        <ExternalLink className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
                      </div>
                      
                      {workflow.description && (
                        <p className="text-sm text-muted-foreground mb-2 line-clamp-2">
                          {workflow.description}
                        </p>
                      )}
                      
                      <div className="flex items-center gap-3 flex-wrap">
                        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-green-100 text-green-700 rounded-md text-xs font-medium">
                          {getIcon(integration.icon, "w-3.5 h-3.5")}
                          <span>
                            Used {workflow.usageCount}x
                          </span>
                        </div>
                        
                        {workflow.executionState ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-blue-100 text-blue-700 rounded-md text-xs font-medium">
                            <Sparkles className="w-3.5 h-3.5" />
                            Active
                          </span>
                        ) : (
                          <span className="inline-flex px-2.5 py-1 bg-muted text-muted-foreground rounded-md text-xs font-medium">
                            Draft
                          </span>
                        )}
                        
                        {workflow.updated_at && (
                          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                            <Clock className="w-3.5 h-3.5" />
                            Updated {format(new Date(workflow.updated_at), "MMM d, yyyy")}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default IntegrationWorkflowsDialog;
