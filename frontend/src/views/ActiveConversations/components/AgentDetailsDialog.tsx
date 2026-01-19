import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/dialog";
import { Button } from "@/components/button";
import { 
  MessageCircleMore, 
  CircleCheckBig, 
  Clock, 
  DollarSign,
  Edit,
  SquareCode,
  KeyRoundIcon,
  Sparkles,
  ChevronDown,
  ChevronRight,
  Activity,
  Boxes,
  Zap,
} from "lucide-react";
import { getWorkflowById } from "@/services/workflows";
import { Workflow } from "@/interfaces/workflow.interface";
import { format } from "date-fns";

interface AgentStats {
  id: string;
  name: string;
  conversationsToday: number;
  resolutionRate: number;
  avgResponseTime: string;
  costPerConversation: number;
  description?: string;
  isActive?: boolean;
  welcomeMessage?: string;
  possibleQueries?: string[];
  workflowId?: string;
}

interface AgentDetailsDialogProps {
  agent: AgentStats | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onManageKeys?: (agentId: string) => void;
}

export function AgentDetailsDialog({
  agent,
  open,
  onOpenChange,
  onManageKeys,
}: AgentDetailsDialogProps) {
  const navigate = useNavigate();
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedSections, setExpandedSections] = useState({
    welcome: true,
    queries: true,
    workflow: true,
  });

  useEffect(() => {
    if (!open || !agent?.workflowId) {
      setWorkflow(null);
      return;
    }

    const fetchWorkflow = async () => {
      setLoading(true);
      setError(null);

      try {
        const workflowData = await getWorkflowById(agent.workflowId!);
        setWorkflow(workflowData);
      } catch (err) {
        console.error("Error fetching workflow:", err);
        setError("Failed to load workflow details");
      } finally {
        setLoading(false);
      }
    };

    fetchWorkflow();
  }, [open, agent?.workflowId]);

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  const getNodeCategoryCounts = () => {
    if (!workflow?.nodes) return null;

    const categories = {
      llm: 0,
      tools: 0,
      integrations: 0,
      other: 0,
    };

    workflow.nodes.forEach((node) => {
      const type = node.type || "";
      if (type.includes("model") || type.includes("agent") || type.includes("mcp")) {
        categories.llm++;
      } else if (
        type.includes("gmail") ||
        type.includes("slack") ||
        type.includes("whatsapp") ||
        type.includes("zendesk") ||
        type.includes("calendar") ||
        type.includes("jira")
      ) {
        categories.integrations++;
      } else if (
        type.includes("tool") ||
        type.includes("knowledge") ||
        type.includes("sql") ||
        type.includes("python") ||
        type.includes("api")
      ) {
        categories.tools++;
      } else {
        categories.other++;
      }
    });

    return categories;
  };

  const getNodeTypesBadges = () => {
    if (!workflow?.nodes) return [];

    const nodeTypes = new Set<string>();
    workflow.nodes.forEach((node) => {
      const type = node.type || "";
      const data = node.data as any;

      // Extract meaningful labels
      if (type.includes("model") && data?.model) {
        nodeTypes.add(data.model);
      } else if (type.includes("knowledge")) {
        nodeTypes.add("Knowledge Base");
      } else if (type.includes("gmail")) {
        nodeTypes.add("Gmail");
      } else if (type.includes("slack")) {
        nodeTypes.add("Slack");
      } else if (type.includes("whatsapp")) {
        nodeTypes.add("WhatsApp");
      } else if (type.includes("zendesk")) {
        nodeTypes.add("Zendesk");
      } else if (type.includes("calendar")) {
        nodeTypes.add("Calendar");
      } else if (type.includes("jira")) {
        nodeTypes.add("Jira");
      } else if (type.includes("sql")) {
        nodeTypes.add("SQL");
      } else if (type.includes("python")) {
        nodeTypes.add("Python");
      }
    });

    return Array.from(nodeTypes).slice(0, 5); // Limit to 5 badges
  };

  const handleEditWorkflow = () => {
    if (agent?.id) {
      navigate(`/ai-agents/workflow/${agent.id}`);
      onOpenChange(false);
    }
  };

  const handleViewIntegration = () => {
    if (agent?.id) {
      navigate(`/ai-agents/integration/${agent.id}`);
      onOpenChange(false);
    }
  };

  const handleManageKeys = () => {
    if (agent?.id && onManageKeys) {
      onManageKeys(agent.id);
      onOpenChange(false);
    }
  };

  if (!agent) return null;

  const nodeCounts = getNodeCategoryCounts();
  const nodeTypeBadges = getNodeTypesBadges();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <DialogTitle className="text-xl">{agent.name}</DialogTitle>
                {agent.isActive ? (
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-green-100 text-green-700 rounded-md text-xs font-medium">
                    <Activity className="w-3.5 h-3.5" />
                    Active
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-gray-100 text-gray-700 rounded-md text-xs font-medium">
                    Inactive
                  </span>
                )}
              </div>
              {agent.description && (
                <DialogDescription className="text-sm">
                  {agent.description}
                </DialogDescription>
              )}
            </div>
          </div>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto space-y-6 pr-2">
          {/* Performance Metrics Grid */}
          <div>
            <h3 className="text-sm font-semibold text-foreground mb-3">
              Performance Metrics
            </h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-muted/50 rounded-lg p-4 border border-border">
                <div className="flex items-center gap-2 mb-2">
                  <MessageCircleMore className="w-4 h-4 text-blue-600" />
                  <span className="text-xs text-muted-foreground">
                    Conversations Today
                  </span>
                </div>
                <p className="text-2xl font-semibold text-foreground pl-5">
                  {agent.conversationsToday}
                </p>
              </div>

              <div className="bg-muted/50 rounded-lg p-4 border border-border">
                <div className="flex items-center gap-2 mb-2">
                  <CircleCheckBig className="w-4 h-4 text-green-600" />
                  <span className="text-xs text-muted-foreground">
                    Resolution Rate
                  </span>
                </div>
                <p className="text-2xl font-semibold text-foreground pl-5">
                  {agent.resolutionRate}%
                </p>
              </div>

              <div className="bg-muted/50 rounded-lg p-4 border border-border">
                <div className="flex items-center gap-2 mb-2">
                  <Clock className="w-4 h-4 text-orange-600" />
                  <span className="text-xs text-muted-foreground">
                    Avg Response Time
                  </span>
                </div>
                <p className="text-2xl font-semibold text-foreground pl-5">
                  {agent.avgResponseTime}
                </p>
              </div>

              <div className="bg-muted/50 rounded-lg p-4 border border-border">
                <div className="flex items-center gap-2 mb-2">
                  <DollarSign className="w-4 h-4 text-purple-600" />
                  <span className="text-xs text-muted-foreground">
                    Cost per Conversation
                  </span>
                </div>
                <p className="text-2xl font-semibold text-foreground pl-5">
                  ${agent.costPerConversation}
                </p>
              </div>
            </div>
          </div>

          {/* Configuration Overview */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-foreground">
              Configuration
            </h3>

            {/* Welcome Message */}
            {agent.welcomeMessage && (
              <div className="border border-border rounded-lg overflow-hidden">
                <button
                  onClick={() => toggleSection("welcome")}
                  className="w-full flex items-center justify-between px-4 py-3 bg-muted/30 hover:bg-muted/50 transition-colors"
                >
                  <span className="text-sm font-medium text-foreground">
                    Welcome Message
                  </span>
                  {expandedSections.welcome ? (
                    <ChevronDown className="w-4 h-4 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-muted-foreground" />
                  )}
                </button>
                {expandedSections.welcome && (
                  <div className="px-4 py-3 bg-white">
                    <p className="text-sm text-muted-foreground">
                      {agent.welcomeMessage}
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Possible Queries */}
            {agent.possibleQueries && agent.possibleQueries.length > 0 && (
              <div className="border border-border rounded-lg overflow-hidden">
                <button
                  onClick={() => toggleSection("queries")}
                  className="w-full flex items-center justify-between px-4 py-3 bg-muted/30 hover:bg-muted/50 transition-colors"
                >
                  <span className="text-sm font-medium text-foreground">
                    Example Queries ({agent.possibleQueries.length})
                  </span>
                  {expandedSections.queries ? (
                    <ChevronDown className="w-4 h-4 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-muted-foreground" />
                  )}
                </button>
                {expandedSections.queries && (
                  <div className="px-4 py-3 bg-white">
                    <ul className="space-y-2">
                      {agent.possibleQueries.map((query, index) => (
                        <li
                          key={index}
                          className="text-sm text-muted-foreground flex items-start gap-2"
                        >
                          <span className="text-blue-600 mt-1">•</span>
                          <span>{query}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Workflow Information */}
          {agent.workflowId && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-foreground">
                Workflow Details
              </h3>

              <div className="border border-border rounded-lg overflow-hidden">
                <button
                  onClick={() => toggleSection("workflow")}
                  className="w-full flex items-center justify-between px-4 py-3 bg-muted/30 hover:bg-muted/50 transition-colors"
                >
                  <span className="text-sm font-medium text-foreground">
                    Workflow Information
                  </span>
                  {expandedSections.workflow ? (
                    <ChevronDown className="w-4 h-4 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-muted-foreground" />
                  )}
                </button>

                {expandedSections.workflow && (
                  <div className="px-4 py-3 bg-white space-y-4">
                    {loading ? (
                      <div className="space-y-2">
                        <div className="h-4 bg-gray-200 rounded animate-pulse" />
                        <div className="h-4 bg-gray-200 rounded animate-pulse w-3/4" />
                      </div>
                    ) : error ? (
                      <p className="text-sm text-red-600">{error}</p>
                    ) : workflow ? (
                      <>
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <p className="text-sm font-medium text-foreground mb-1">
                              {workflow.name}
                            </p>
                            {workflow.description && (
                              <p className="text-xs text-muted-foreground">
                                {workflow.description}
                              </p>
                            )}
                          </div>
                          {workflow.executionState ? (
                            <span className="inline-flex items-center gap-1 px-2 py-1 bg-blue-100 text-blue-700 rounded-md text-xs font-medium">
                              <Sparkles className="w-3 h-3" />
                              Active
                            </span>
                          ) : (
                            <span className="inline-flex px-2 py-1 bg-gray-100 text-gray-700 rounded-md text-xs font-medium">
                              Draft
                            </span>
                          )}
                        </div>

                        {/* Node Categories */}
                        {nodeCounts && (
                          <div className="flex items-center gap-3 flex-wrap">
                            {nodeCounts.llm > 0 && (
                              <div className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-purple-100 text-purple-700 rounded-md text-xs font-medium">
                                <Zap className="w-3.5 h-3.5" />
                                {nodeCounts.llm} LLM
                              </div>
                            )}
                            {nodeCounts.tools > 0 && (
                              <div className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-blue-100 text-blue-700 rounded-md text-xs font-medium">
                                <Boxes className="w-3.5 h-3.5" />
                                {nodeCounts.tools} Tools
                              </div>
                            )}
                            {nodeCounts.integrations > 0 && (
                              <div className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-green-100 text-green-700 rounded-md text-xs font-medium">
                                <Activity className="w-3.5 h-3.5" />
                                {nodeCounts.integrations} Integrations
                              </div>
                            )}
                          </div>
                        )}

                        {/* Node Type Badges */}
                        {nodeTypeBadges.length > 0 && (
                          <div>
                            <p className="text-xs text-muted-foreground mb-2">
                              Components:
                            </p>
                            <div className="flex items-center gap-2 flex-wrap">
                              {nodeTypeBadges.map((badge, index) => (
                                <span
                                  key={index}
                                  className="inline-flex px-2 py-1 bg-muted text-foreground rounded text-xs"
                                >
                                  {badge}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Last Updated */}
                        {workflow.updated_at && (
                          <div className="flex items-center gap-1 text-xs text-muted-foreground pt-2 border-t border-border">
                            <Clock className="w-3.5 h-3.5" />
                            Last updated{" "}
                            {format(new Date(workflow.updated_at), "MMM d, yyyy 'at' h:mm a")}
                          </div>
                        )}
                      </>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        No workflow details available
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Quick Actions Footer */}
        <div className="pt-4 flex items-center justify-end gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleEditWorkflow}
            className="gap-2"
          >
            <Edit className="w-4 h-4" />
            Edit Workflow
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleViewIntegration}
            className="gap-2"
          >
            <SquareCode className="w-4 h-4" />
            Integration
          </Button>
          {onManageKeys && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleManageKeys}
              className="gap-2"
            >
              <KeyRoundIcon className="w-4 h-4" />
              API Keys
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default AgentDetailsDialog;
