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

export const nodeBgColors: Record<string, string> = {
  io: "bg-brand-50",
  ai: "bg-pink-50",
  routing: "bg-orange-50",
  integrations: "bg-green-50",
  formatting: "bg-purple-50",
  tools: "bg-sky-50",
  training: "bg-rose-50",
  default: "bg-brand-50",
};

export const getNodeBgColor = (nodeCategory: string): string => {
  return nodeBgColors[nodeCategory] || nodeBgColors.default;
};

export const nodeIconColors: Record<string, string> = {
  io: "text-brand-600",
  ai: "text-pink-600",
  routing: "text-orange-500",
  integrations: "text-green-600",
  formatting: "text-purple-600",
  tools: "text-sky-600",
  training: "text-rose-600",
  default: "text-brand-600",
};

export const getNodeIconColor = (nodeCategory: string): string => {
  return nodeIconColors[nodeCategory] || nodeIconColors.default;
};
