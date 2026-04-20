import React from "react";
import { CircleHelp, MoreVertical, Play, Settings, Trash2 } from "lucide-react";
import { Button } from "@/components/button";
import { CardHeader } from "@/components/card";
import { renderIcon } from "../utils/iconUtils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/dropdown-menu";

interface NodeHeaderProps {
  iconName: string;
  title: string;
  subtitle: string;
  color: string;
  hasError?: boolean;
  isSpecialNode?: boolean;
  onSettings?: () => void;
  onTest?: () => void;
  onHelpClick?: () => void;
  onDeleteClick: () => void;
}

const NodeHeader: React.FC<NodeHeaderProps> = ({
  iconName,
  title,
  subtitle,
  color,
  hasError,
  isSpecialNode,
  onSettings,
  onTest,
  onHelpClick,
  onDeleteClick: onDeleteClick,
}) => {
  const isSpecialNoError = isSpecialNode && !hasError;

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
                isSpecialNoError ? "white" : "accent-foreground"
              } truncate`}
            >
              {title}
            </h3>
            <p
              className={`text-xs text-${
                isSpecialNoError ? "white" : "muted-foreground"
              } truncate`}
            >
              {subtitle}
            </p>
          </div>
        </div>
        <div className="flex items-center space-x-1 nodrag nopan pointer-events-auto">
          {onSettings && (
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8 text-accent-foreground hover:bg-white"
              onClick={onSettings}
              data-node-settings
            >
              <Settings className="h-4 w-4" />
            </Button>
          )}
          {onTest && (
            <Button
              size="icon"
              variant="ghost"
              className={`h-8 w-8 text-${
                isSpecialNoError ? "white" : "accent-foreground"
              } hover:bg-white`}
              onClick={onTest}
            >
              <Play className="h-4 w-4" />
            </Button>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                size="icon"
                variant="ghost"
                className={`h-8 w-8 text-${
                  isSpecialNoError ? "white" : "accent-foreground"
                } hover:bg-white`}
              >
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" sideOffset={6} className="z-[2100] min-w-[140px]">
              <DropdownMenuItem
                onSelect={() => onHelpClick?.()}
                disabled={!onHelpClick}
              >
                <CircleHelp className="mr-2 h-4 w-4" />
                Help
              </DropdownMenuItem>
              <DropdownMenuItem
                onSelect={onDeleteClick}
                className="text-red-600 focus:bg-red-50 focus:text-red-700"
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </CardHeader>
  );
};

export default NodeHeader;
