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
  onSettings?: () => void;
  onTest?: () => void;
  onDeleteClick: () => void;
}

const NodeHeader: React.FC<NodeHeaderProps> = ({
  iconName,
  title,
  subtitle,
  color,
  onSettings,
  onTest,
  onDeleteClick: onDeleteClick,
}) => {
  const titleColor = "#18181B";
  const subtitleColor = "#71717A";

  return (
    <CardHeader className="relative overflow-hidden">
      <div className="flex items-center justify-between relative z-10">
        <div className="flex items-center space-x-3">
          <div
            className="p-2 rounded-lg backdrop-blur-sm"
            style={{ backgroundColor: color }}
          >
            {renderIcon(iconName, "h-4 w-4 text-white")}
          </div>
          <div>
            <h3 className="text-sm font-semibold" style={{ color: titleColor }}>
              {title}
            </h3>
            <p className="text-xs" style={{ color: subtitleColor }}>
              {subtitle}
            </p>
          </div>
        </div>
        <div className="flex items-center space-x-1">
          {onSettings && (
            <Button
              size="icon"
              variant="ghost"
              className={`h-8 w-8 ${titleColor} hover:bg-white`}
              onClick={onSettings}
            >
              <Settings className="h-4 w-4" />
            </Button>
          )}
          {onTest && (
            <Button
              size="icon"
              variant="ghost"
              className={`h-8 w-8 ${titleColor} hover:bg-white`}
              onClick={onTest}
            >
              <Play className="h-4 w-4" />
            </Button>
          )}
          <Button
            size="icon"
            variant="ghost"
            className={`h-8 w-8 ${titleColor} hover:bg-white`}
            onClick={onDeleteClick}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="absolute inset-0 opacity-10">
        <div className="absolute -right-4 -top-4 w-24 h-24 rounded-full bg-white/20"></div>
        <div className="absolute -left-2 -bottom-2 w-16 h-16 rounded-full bg-white/10"></div>
      </div>
    </CardHeader>
  );
};

export default NodeHeader;
