export const nodeColors: Record<string, string> = {
  io: "brand-600",
  ai: "pink-600",
  routing: "orange-500",
  integrations: "green-600",
  formatting: "purple-600",
  tools: "sky-600",
  training: "rose-600",
  audio: "teal-600",
  default: "brand-600",
};

export const getNodeColor = (nodeCategory: string): string => {
  return nodeColors[nodeCategory] || nodeColors.default;
};

// Light mode keeps the soft pastel tint; dark mode uses a SOLID (opaque) dark
// shade of the category's own color — same hue as the icon, no transparency, so
// the canvas grid never shows through the header. These are the flattened
// equivalents of the saturated color at ~20% over the dark canvas. The classes
// are literal here so Tailwind picks up the arbitrary values without a safelist.
export const nodeBgColors: Record<string, string> = {
  io: "bg-brand-50 dark:bg-[#0c1438]",
  ai: "bg-pink-50 dark:bg-[#330f21]",
  routing: "bg-orange-50 dark:bg-[#391e0d]",
  integrations: "bg-green-50 dark:bg-[#0c2818]",
  formatting: "bg-purple-50 dark:bg-[#251238]",
  tools: "bg-sky-50 dark:bg-[#082231]",
  training: "bg-rose-50 dark:bg-[#340d17]",
  audio: "bg-teal-50 dark:bg-[#0a2524]",
  default: "bg-brand-50 dark:bg-[#0c1438]",
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
  audio: "text-teal-600",
  default: "text-brand-600",
};

export const getNodeIconColor = (nodeCategory: string): string => {
  return nodeIconColors[nodeCategory] || nodeIconColors.default;
};
