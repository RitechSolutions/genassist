import React from "react";
import {
  HelpCircle,
  Tag,
  MessageCircle,
  MessageSquare,
  Globe,
  Mail,
  Code,
  ArrowLeftRight,
  Database,
  Share2,
  FileText,
  Brain,
  Wrench,
  MailOpen,
  Calendar,
  Split,
  Merge,
  Send,
  ArrowRightFromLine,
  ArrowRightToLine,
  Bot,
  CircleAlert,
  Search,
  GitBranch,
} from "lucide-react";
import SlackLogo from "@/assets/slack-logo.png";
import WhatsAppLogo from "@/assets/whatsapp-logo.png";
import JiraLogo from "@/assets/jira-logo.png";
import ZendeskLogo from "@/assets/zendesk-logo.png";

// Types for icon configuration
export type IconType = "lucide" | "asset";

export interface IconConfig {
  type: IconType;
  source: React.ComponentType<{ className?: string }> | string;
}

// Icon mapping configuration
export const ICON_MAPPING: Record<string, IconConfig> = {
  // Lucide icons
  CircleAlert: { type: "lucide", source: CircleAlert },
  MessageCircle: { type: "lucide", source: MessageCircle },
  MessageSquare: { type: "lucide", source: MessageSquare },
  Tag: { type: "lucide", source: Tag },
  Globe: { type: "lucide", source: Globe },
  Search: { type: "lucide", source: Search },
  Mail: { type: "lucide", source: Mail },
  Code: { type: "lucide", source: Code },
  ArrowLeftRight: { type: "lucide", source: ArrowLeftRight },
  Database: { type: "lucide", source: Database },
  Share2: { type: "lucide", source: Share2 },
  FileText: { type: "lucide", source: FileText },
  Brain: { type: "lucide", source: Brain },
  Wrench: { type: "lucide", source: Wrench },
  MailOpen: { type: "lucide", source: MailOpen },
  Calendar: { type: "lucide", source: Calendar },
  Split: { type: "lucide", source: Split },
  SplitRotated: {
    type: "lucide",
    source: (props) => (
      <Split {...props} style={{ transform: "rotate(90deg)" }} />
    ),
  },
  Merge: { type: "lucide", source: Merge },
  MergeRotated: {
    type: "lucide",
    source: (props) => (
      <Merge {...props} style={{ transform: "rotate(90deg)" }} />
    ),
  },
  Send: { type: "lucide", source: Send },
  ArrowRightFromLine: { type: "lucide", source: ArrowRightFromLine },
  ArrowRightToLine: { type: "lucide", source: ArrowRightToLine },
  Bot: { type: "lucide", source: Bot },
  Workflow: { type: "lucide", source: GitBranch },
  GitBranch: { type: "lucide", source: GitBranch },

  // Custom asset icons
  Slack: { type: "asset", source: SlackLogo },
  Whatsapp: { type: "asset", source: WhatsAppLogo },
  Jira: { type: "asset", source: JiraLogo },
  Zendesk: { type: "asset", source: ZendeskLogo },

  // Legacy kebab-case mappings for backward compatibility
  "message-circle": { type: "lucide", source: MessageCircle },
  "message-square": { type: "lucide", source: MessageSquare },
  tag: { type: "lucide", source: Tag },
  globe: { type: "lucide", source: Globe },
  mail: { type: "lucide", source: Mail },
  code: { type: "lucide", source: Code },
  "arrow-left-right": { type: "lucide", source: ArrowLeftRight },
  database: { type: "lucide", source: Database },
  share: { type: "lucide", source: Share2 },
  "file-text": { type: "lucide", source: FileText },
  brain: { type: "lucide", source: Brain },
  wrench: { type: "lucide", source: Wrench },
};

// Default fallback icon
const DEFAULT_ICON = { type: "lucide" as const, source: HelpCircle };

// Renders an icon from either Lucide React or custom assets
export const renderIcon = (
  iconName: string,
  className: string = "h-4 w-4 text-white",
  style?: React.CSSProperties
) => {
  const iconConfig = ICON_MAPPING[iconName] || DEFAULT_ICON;

  if (iconConfig.type === "lucide") {
    const IconComponent = iconConfig.source as React.ComponentType<{
      className?: string;
    }>;
    return <IconComponent className={className} />;
  } else {
    // Asset image
    const imageSrc = iconConfig.source as string;

    // Determine if this is for a panel (sidebar) based on className
    const isPanelIcon =
      className.includes("text-") && !className.includes("text-white");

    // For panel icons, we want to use colored images, for node headers we want white
    const imageStyle: React.CSSProperties = {
      objectFit: "contain",
      ...style,
    };

    // Apply white filter only for node headers (text-white), not for panel icons
    if (className.includes("text-white")) {
      imageStyle.filter = "brightness(0) invert(1)"; // Make image white
    }

    return (
      <img
        src={imageSrc}
        alt={`${iconName} icon`}
        className={className.replace(/text-\S+/g, "")} // Remove all text color classes for images
        style={imageStyle}
      />
    );
  }
};

// Get available icon names for type checking
export type UnifiedIconName = keyof typeof ICON_MAPPING;

// Check if an icon exists in the mapping
export const hasIcon = (iconName: string): iconName is UnifiedIconName => {
  return iconName in ICON_MAPPING;
};

// Helper function to get icon name from node definition
export const getNodeIcon = (
  nodeRegistry: {
    getNodeType: (type: string) => { icon?: string } | undefined;
  },
  nodeType: string,
  fallbackIcon: string = "MessageCircle"
): string => {
  const nodeDefinition = nodeRegistry.getNodeType(nodeType);
  return nodeDefinition?.icon || fallbackIcon;
};
