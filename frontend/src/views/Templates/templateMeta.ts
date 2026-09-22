import type { ElementType } from "react";
import {
  BookOpen,
  FileText,
  Headphones,
  Mail,
  MessageCircle,
  MessageSquare,
  Sparkles,
} from "lucide-react";

/**
 * Category color coding. The default and the primary "Support" domain resolve to
 * the app's own brand token (`hsl(var(--primary))`) so they stay on-brand and
 * theme-aware; the remaining domains get complementary hues since the design
 * system defines none for them.
 */
export const CATEGORY_COLORS: Record<string, string> = {
  "customer support": "hsl(var(--primary))",
  support: "hsl(var(--primary))",
  knowledge: "#6366F1", // indigo
  hr: "#8B5CF6", // violet
  "human resources": "#8B5CF6",
  productivity: "#F59E0B", // amber
  messaging: "#10B981", // emerald
  sales: "#F43F5E", // rose
};

export function categoryColor(category?: string | null): string {
  if (!category) return "hsl(var(--primary))";
  return CATEGORY_COLORS[category.trim().toLowerCase()] ?? "hsl(var(--primary))";
}

const ICONS: Record<string, ElementType> = {
  Headphones,
  BookOpen,
  MessageSquare,
  MessageCircle,
  Mail,
  FileUser: FileText,
  FileText,
  Sparkles,
};

export function iconFor(name?: string | null): ElementType {
  return (name && ICONS[name]) || Sparkles;
}

/** Human-readable capability labels for raw workflow node types. */
const NODE_LABELS: Record<string, string> = {
  agentNode: "Agent",
  externalAgentNode: "Agent",
  voiceAgentNode: "Voice",
  llmModelNode: "LLM",
  knowledgeBaseNode: "Knowledge",
  threadRAGNode: "RAG",
  slackMessageNode: "Slack",
  whatsappToolNode: "WhatsApp",
  whatsappMessageNode: "WhatsApp",
  gmailNode: "Email",
  readMailsNode: "Email",
  zendeskTicketNode: "Zendesk",
  salesforceCaseNode: "Salesforce",
  jiraNode: "Jira",
  calendarEventNode: "Calendar",
  routerNode: "Router",
  sqlNode: "SQL",
  apiToolNode: "API",
  openApiNode: "API",
  pythonCodeNode: "Python",
  pythonToolNode: "Python",
  toolBuilderNode: "Tools",
  mcpNode: "MCP",
  ttsNode: "Voice",
  sttNode: "Voice",
  nlpNode: "NLP",
  webScraperNode: "Web",
  humanInTheLoopNode: "Human",
  guardrailNliNode: "Guardrail",
  guardrailProvenanceNode: "Guardrail",
  workflowExecutorNode: "Sub-flow",
};

export function nodeLabel(type: string): string {
  return NODE_LABELS[type] ?? type.replace(/Node$/, "");
}

// Structural/plumbing nodes that don't communicate a capability to a buyer.
const STRUCTURAL = new Set([
  "chatInputNode",
  "chatOutputNode",
  "templateNode",
  "setStateNode",
  "dataMapperNode",
  "aggregatorNode",
  "finalizeConversationNode",
]);

export function capabilities(nodeTypes: string[]): string[] {
  const pick = (types: string[]): string[] => {
    const out: string[] = [];
    const seen = new Set<string>();
    for (const type of types) {
      const label = nodeLabel(type);
      if (!seen.has(label)) {
        seen.add(label);
        out.push(label);
      }
    }
    return out;
  };
  const meaningful = pick(nodeTypes.filter((type) => !STRUCTURAL.has(type)));
  return meaningful.length ? meaningful : pick(nodeTypes);
}
