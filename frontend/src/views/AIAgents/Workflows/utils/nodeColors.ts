export type NodeColor = {
  icon: string;
  header: string;
  hover: string;
  focus: string;
  placeholder: string;
  panelIcon: string;
};

export const nodeColors1: Record<string, NodeColor> = {
  chatInputNode: {
    icon: "text-blue-500",
    header: "bg-blue-400",
    hover: "hover:bg-blue-600",
    focus: "focus:border-white focus:bg-blue-600",
    placeholder: "placeholder:text-blue-200",
    panelIcon: "text-blue-500",
  },
  llmModelNode: {
    icon: "text-purple-500",
    header: "bg-purple-400",
    hover: "hover:bg-purple-600",
    focus: "focus:border-white focus:bg-purple-600",
    placeholder: "placeholder:text-purple-200",
    panelIcon: "text-purple-500",
  },
  promptNode: {
    icon: "text-green-500",
    header: "bg-green-400",
    hover: "hover:bg-green-600",
    focus: "focus:border-white focus:bg-green-600",
    placeholder: "placeholder:text-green-200",
    panelIcon: "text-green-500",
  },
  chatOutputNode: {
    icon: "text-orange-500",
    header: "bg-orange-400",
    hover: "hover:bg-orange-600",
    focus: "focus:border-white focus:bg-orange-600",
    placeholder: "placeholder:text-orange-200",
    panelIcon: "text-orange-500",
  },
  apiToolNode: {
    icon: "text-blue-500",
    header: "bg-blue-400",
    hover: "hover:bg-blue-600",
    focus: "focus:border-white focus:bg-blue-600",
    placeholder: "placeholder:text-blue-200",
    panelIcon: "text-blue-500",
  },
  agentNode: {
    icon: "text-purple-500",
    header: "bg-purple-400",
    hover: "hover:bg-purple-600",
    focus: "focus:border-white focus:bg-purple-600",
    placeholder: "placeholder:text-purple-200",
    panelIcon: "text-purple-500",
  },
  knowledgeBaseNode: {
    icon: "text-indigo-500",
    header: "bg-indigo-400",
    hover: "hover:bg-indigo-600",
    focus: "focus:border-white focus:bg-indigo-600",
    placeholder: "placeholder:text-indigo-200",
    panelIcon: "text-indigo-500",
  },
  mapperNode: {
    icon: "text-gray-500",
    header: "bg-gray-400",
    hover: "hover:bg-gray-600",
    focus: "focus:border-white focus:bg-gray-600",
    placeholder: "placeholder:text-gray-200",
    panelIcon: "text-gray-500",
  },
  default: {
    icon: "text-gray-500",
    header: "bg-gray-400",
    hover: "hover:bg-gray-600",
    focus: "focus:border-white focus:bg-gray-600",
    placeholder: "placeholder:text-gray-200",
    panelIcon: "text-gray-500",
  },
};

export const nodeColors2: Record<string, NodeColor> = {
  chatInputNode: {
    icon: "text-gray-500",
    header: "bg-gray-400",
    hover: "hover:bg-gray-600",
    focus: "focus:border-white focus:bg-gray-600",
    placeholder: "placeholder:text-gray-200",
    panelIcon: "text-gray-500",
  },
  llmModelNode: {
    icon: "text-black",
    header: "bg-black",
    hover: "hover:bg-black",
    focus: "focus:border-white focus:bg-black",
    placeholder: "placeholder:text-black",
    panelIcon: "text-black",
  },
  promptNode: {
    icon: "text-indigo-500",
    header: "bg-indigo-400",
    hover: "hover:bg-indigo-600",
    focus: "focus:border-white focus:bg-indigo-600",
    placeholder: "placeholder:text-indigo-200",
    panelIcon: "text-indigo-500",
  },
  chatOutputNode: {
    icon: "text-gray-500",
    header: "bg-gray-400",
    hover: "hover:bg-gray-600",
    focus: "focus:border-white focus:bg-gray-600",
    placeholder: "placeholder:text-gray-200",
    panelIcon: "text-gray-500",
  },
  apiToolNode: {
    icon: "text-blue-500",
    header: "bg-blue-400",
    hover: "hover:bg-blue-600",
    focus: "focus:border-white focus:bg-blue-600",
    placeholder: "placeholder:text-blue-200",
    panelIcon: "text-blue-500",
  },
  agentNode: {
    icon: "text-black",
    header: "bg-black",
    hover: "hover:bg-black",
    focus: "focus:border-white focus:bg-black",
    placeholder: "placeholder:text-black",
    panelIcon: "text-black",
  },
  knowledgeBaseNode: {
    icon: "text-green-500",
    header: "bg-green-400",
    hover: "hover:bg-green-600",
    focus: "focus:border-white focus:bg-green-600",
    placeholder: "placeholder:text-green-200",
    panelIcon: "text-green-500",
  },
  mapperNode: {
    icon: "text-gray-500",
    header: "bg-gray-400",
    hover: "hover:bg-gray-600",
    focus: "focus:border-white focus:bg-gray-600",
    placeholder: "placeholder:text-gray-200",
    panelIcon: "text-gray-500",
  },
  default: {
    icon: "text-gray-500",
    header: "bg-gray-400",
    hover: "hover:bg-gray-600",
    focus: "focus:border-white focus:bg-gray-600",
    placeholder: "placeholder:text-gray-200",
    panelIcon: "text-gray-500",
  },
};
export const nodeColors = nodeColors2;
export const getNodeColors = (nodeType: string): NodeColor => {
  return nodeColors[nodeType] || nodeColors.default;
};
