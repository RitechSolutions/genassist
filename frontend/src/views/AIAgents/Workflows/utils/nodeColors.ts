export const nodeColors: Record<string, string> = {
  io: "#4F46E5",
  ai: "#DB2777",
  routing: "#F97316",
  integrations: "#16A34A",
  formatting: "#9333EA",
  tools: "#0284C7",
  training: "#E11D48",
  default: "#4F46E5",
};

export const getNodeColor = (nodeCategory: string): string => {
  return nodeColors[nodeCategory] || nodeColors.default;
};

// export type NodeColor = {
//   icon: string;
//   header: string;
//   hover: string;
//   focus: string;
//   placeholder: string;
//   panelIcon: string;
// };

// const createColor = (base: string, shade: number = 500): NodeColor => ({
//   icon: `text-${base}${base !== "black" ? `-${shade}` : ""}`,
//   header: `bg-${base}${base !== "black" ? `-${shade - 100}` : ""}`,
//   hover: `hover:bg-${base}${base !== "black" ? `-${shade + 100}` : ""}`,
//   focus: `focus:border-white focus:bg-${base}${
//     base !== "black" ? `-${shade + 100}` : ""
//   }`,
//   placeholder: `placeholder:text-${base}${base !== "black" ? "-200" : ""}`,
//   panelIcon: `text-${base}${base !== "black" ? `-${shade}` : ""}`,
// });

// export const nodeColors: Record<string, NodeColor> = {
//   chatInputNode: createColor("gray"),
//   llmModelNode: createColor("black"),
//   templateNode: createColor("indigo"),
//   chatOutputNode: createColor("gray"),
//   apiToolNode: createColor("blue"),
//   agentNode: createColor("black"),
//   knowledgeBaseNode: createColor("green"),
//   zendeskTicketNode: createColor("orange"),
//   gmailNode: createColor("blue", 600),
//   readMailsNode: createColor("purple"),
//   pythonCodeNode: createColor("orange"),
//   toolBuilderNode: createColor("teal"),
//   calendarEventNode: createColor("teal"),
//   slackMessageNode: createColor("blue"),
//   whatsappToolNode: createColor("green", 600),
//   sqlNode: createColor("cyan"),
//   jiraNode: createColor("blue"),
//   mlModelInferenceNode: createColor("pink"),
//   trainDataSourceNode: createColor("cyan"),
//   preprocessingNode: createColor("orange"),
//   trainModelNode: createColor("purple"),
//   default: createColor("gray"),
// };
