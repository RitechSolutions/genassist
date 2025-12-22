export const nodeColors: Record<string, string> = {
  io: "brand-600",
  ai: "pink-600",
  routing: "orange-500",
  integrations: "green-600",
  formatting: "purple-600",
  tools: "sky-600",
  training: "rose-600",
  default: "brand-600",
};

export const getNodeColor = (nodeCategory: string): string => {
  return nodeColors[nodeCategory] || nodeColors.default;
};
