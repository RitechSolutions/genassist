import React from "react";
import { MoreVertical, Play, Settings, Trash2 } from "lucide-react";
import { Button } from "@/components/button";
import { CardHeader } from "@/components/card";
import { renderIcon } from "../utils/iconUtils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/RadixTooltip";
import NodeActionsMenu from "../components/NodeActionsMenu";

interface NodeHeaderProps {
  iconName: string;
  title: string;
  subtitle: string;
  color: string;
  hasError?: boolean;
  isSpecialNode?: boolean;
  deactivated?: boolean;
  onSettings?: () => void;
  onTest?: () => void;
  onHelpClick?: () => void;
  onToggleActive?: () => void;
  onDeleteClick: () => void;
  onRename: () => void;
  onReplace: () => void;
  onCopy: () => void;
  onDuplicate: () => void;
}

const NodeHeader: React.FC<NodeHeaderProps> = ({
  iconName,
  title,
  subtitle,
  color,
  hasError,
  isSpecialNode,
  deactivated,
  onSettings,
  onTest,
  onHelpClick,
  onToggleActive,
  onDeleteClick: onDeleteClick,
  onRename,
  onReplace,
  onCopy,
  onDuplicate,
}) => {
  const isSpecialNoError = isSpecialNode && !hasError;
  // Header text color. Special I/O nodes have a dark-blue header → white text.
  // Everything else adapts (dark on the light pastel, light on the solid dark header).
  const titleColor = isSpecialNoError ? "white" : "accent-foreground";
  const subtitleColor = isSpecialNoError ? "white" : "muted-foreground";

  return (
    <CardHeader className="relative overflow-hidden">
      <div className="flex items-center justify-between relative z-10">
        <div className="flex items-center space-x-3 flex-1 min-w-0">
          <div
            className={`p-2 rounded-lg backdrop-blur-sm bg-${color} flex-shrink-0`}
          >
            {renderIcon(
              iconName,
              `h-4 w-4 text-${isSpecialNoError ? "brand-600" : "white"}`
            )}
          </div>
          <div className="min-w-0">
            <h3
              className={`text-sm font-semibold text-${
                titleColor
              } truncate`}
            >
              {title}
            </h3>
            <p
              className={`text-xs text-${
                subtitleColor
              } truncate`}
            >
              {subtitle}
            </p>
            {deactivated && (
              <p className="text-xs font-medium italic text-muted-foreground truncate">
                (Deactivated)
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center space-x-1 nodrag nopan pointer-events-auto">
          {/* Order: play - settings - active/inactive - delete - more */}
          {onTest &&
            (deactivated ? (
              <TooltipProvider delayDuration={0}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    {/* A disabled button swallows pointer events, so the span is
                        the hover target that drives the tooltip. */}
                    <span className="inline-flex">
                      <Button
                        size="icon"
                        variant="ghost"
                        className={`h-8 w-8 text-${titleColor} hover:bg-black/10`}
                        disabled
                      >
                        <Play className="h-4 w-4" />
                      </Button>
                    </span>
                  </TooltipTrigger>
                  <TooltipContent side="top">
                    This node is deactivated and can't be run
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            ) : (
              <Button
                size="icon"
                variant="ghost"
                className={`h-8 w-8 text-${titleColor} hover:bg-black/10`}
                onClick={onTest}
              >
                <Play className="h-4 w-4" />
              </Button>
            ))}
          {onSettings && (
            <Button
              size="icon"
              variant="ghost"
              className={`h-8 w-8 text-${titleColor} hover:bg-black/10`}
              onClick={onSettings}
              data-node-settings
            >
              <Settings className="h-4 w-4" />
            </Button>
          )}
          <Button
            size="icon"
            variant="ghost"
            className={`h-8 w-8 text-${titleColor} hover:bg-black/10`}
            onClick={onDeleteClick}
            title="Delete"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
          <NodeActionsMenu
            deactivated={deactivated}
            canModify={!isSpecialNode}
            onConfigure={onSettings}
            onRename={onRename}
            onReplace={onReplace}
            onToggleActive={() => onToggleActive?.()}
            onCopy={onCopy}
            onDuplicate={onDuplicate}
            onHelp={onHelpClick}
            onDelete={onDeleteClick}
            trigger={
              <Button
                size="icon"
                variant="ghost"
                className={`h-8 w-8 text-${titleColor} hover:bg-black/10`}
                title="More actions"
              >
                <MoreVertical className="h-4 w-4" />
              </Button>
            }
          />
        </div>
      </div>
    </CardHeader>
  );
};

export default NodeHeader;
