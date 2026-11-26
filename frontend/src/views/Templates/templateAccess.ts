import { AgentListItem } from "@/interfaces/ai-agent.interface";
import { userHasPermission } from "@/services/auth";

// Template actions the user's role allows. A hidden action is never offered.
export const templateActionAccess = (permissions: string[]) => ({
  use: userHasPermission(permissions, "install:template"),
  // Publish and Withdraw
  publish: userHasPermission(permissions, "publish:template"),
  delete: userHasPermission(permissions, "delete:template"),
  save: userHasPermission(permissions, "create:template"),
});

// Same rule as the server: the user's own agents and system agents, with a workflow.
export const canSaveAgentAsTemplate = (
  agent: Pick<AgentListItem, "is_system" | "is_mine" | "workflow_id">,
  permissions: string[],
): boolean =>
  userHasPermission(permissions, "create:template") &&
  !!agent.workflow_id &&
  (agent.is_system || !!agent.is_mine);
