import React from "react";
import { Play, Settings, Trash2 } from "lucide-react";
import { Button } from "@/components/button";
import { CardHeader } from "@/components/card";
import { renderIcon } from "../utils/iconUtils";

interface NodeHeaderProps {
  iconName: string;
  title: string;
  subtitle: string;
  color: string;
  hasError?: boolean;
  isSpecialNode?: boolean;
  onSettings?: () => void;
  onTest?: () => void;
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
        <div className="flex items-center space-x-1">
          {onSettings && (
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8 text-accent-foreground hover:bg-white"
              onClick={onSettings}
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
          <Button
            size="icon"
            variant="ghost"
            className={`h-8 w-8 text-${
              isSpecialNoError ? "white" : "accent-foreground"
            } hover:bg-white`}
            onClick={onDeleteClick}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </CardHeader>
  );
};

export default NodeHeader;
