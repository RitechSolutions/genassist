import React, { useState } from "react";
import { ChevronDown, ChevronRight, Copy } from "lucide-react";

export interface NodeMetadata {
  [nodeId: string]: {
    name: string;
    type: string;
  };
}

export interface JsonViewerProps {
  data: Record<string, unknown>;
  level?: number;
  onDragStart?: (e: React.DragEvent, path: string, value: unknown) => void;
  basePath?: string;
  nodeMetadata?: NodeMetadata;
}

/**
 * Checks if a string looks like a UUID (node ID)
 */
const isNodeId = (key: string): boolean => {
  const uuidPattern =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  return uuidPattern.test(key);
};

export const JsonViewer: React.FC<JsonViewerProps> = ({
  data,
  level = 0,
  onDragStart,
  basePath = "",
  nodeMetadata = {},
}) => {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const toggleExpanded = (key: string) => {
    setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleDragStart = (
    e: React.DragEvent,
    path: string,
    value: unknown
  ) => {
    if (onDragStart) {
      onDragStart(e, `{{${path}}}`, value);
    }
  };

  const copyPath = (path: string) => {
    const formattedPath = `{{${path}}}`;
    navigator.clipboard.writeText(formattedPath);
  };

  const renderValue = (key: string, value: unknown, currentPath: string) => {
    const isExpanded = expanded[key];
    const hasChildren =
      value &&
      typeof value === "object" &&
      value !== null &&
      !Array.isArray(value) &&
      Object.keys(value as object).length > 0;

    const isArray = Array.isArray(value);
    const hasArrayChildren = isArray && (value as any[]).length > 0;

    // Get display name from nodeMetadata if this is a node ID
    const nodeInfo = isNodeId(key) ? nodeMetadata[key] : null;
    const displayName = nodeInfo ? nodeInfo.name : key;
    const nodeType = nodeInfo?.type;

    // Build tooltip content
    const tooltipText = nodeInfo
      ? `${nodeInfo.name}\nType: ${nodeInfo.type}\nID: ${key}\n\nClick to copy • Drag to input`
      : `${key}\n\nClick to copy • Drag to input`;

    if (hasChildren || hasArrayChildren) {
      const typeLabel = isArray
        ? `Array[${(value as any[]).length}]`
        : nodeType
          ? nodeType
          : "Object";

      return (
        <div key={key} className="ml-2">
          <div className="flex items-center gap-2 py-1 px-2 bg-gray-50 rounded hover:bg-gray-100 transition-colors">
            <button
              onClick={() => toggleExpanded(key)}
              className="text-gray-500 hover:text-blue-600 transition-colors p-1 rounded hover:bg-blue-50 flex-shrink-0"
            >
              {isExpanded ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
            </button>

            {/* Draggable key badge */}
            <div
              draggable
              onDragStart={(e) => handleDragStart(e, currentPath, value)}
              onClick={() => copyPath(currentPath)}
              className="group inline-flex items-center gap-1 px-2 py-0.5 bg-blue-500 hover:bg-blue-600 text-white text-xs font-medium rounded cursor-grab active:cursor-grabbing transition-all duration-200 hover:shadow-sm max-w-[140px]"
              title={tooltipText}
            >
              <span className="truncate">{displayName}</span>
              <Copy className="h-2.5 w-2.5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
            </div>

            <span className="text-gray-400 text-xs">{typeLabel}</span>
            {!isExpanded && <span className="text-gray-300 text-xs">...</span>}
          </div>

          {isExpanded && (
            <div className="ml-4 mt-1 border-l border-gray-200 pl-3 bg-white">
              {isArray ? (
                (value as any[]).map((item, index) => (
                  <JsonViewer
                    key={index}
                    data={{ [index]: item }}
                    level={level + 1}
                    onDragStart={onDragStart}
                    basePath={`${currentPath}[${index}]`}
                    nodeMetadata={nodeMetadata}
                  />
                ))
              ) : (
                <JsonViewer
                  data={value as Record<string, unknown>}
                  level={level + 1}
                  onDragStart={onDragStart}
                  basePath={currentPath}
                  nodeMetadata={nodeMetadata}
                />
              )}
            </div>
          )}
        </div>
      );
    }

    // Handle empty objects and arrays
    if (
      (isArray && (value as any[]).length === 0) ||
      (typeof value === "object" &&
        value !== null &&
        Object.keys(value as object).length === 0)
    ) {
      const typeLabel = isArray ? "Array[]" : "Object{}";

      return (
        <div key={key} className="ml-2">
          <div className="flex items-center gap-2 py-1 px-2 bg-gray-50 rounded hover:bg-gray-100 transition-colors">
            {/* Draggable key badge for empty containers */}
            <div
              draggable
              onDragStart={(e) => handleDragStart(e, currentPath, value)}
              onClick={() => copyPath(currentPath)}
              className="group inline-flex items-center gap-1 px-2 py-0.5 bg-orange-500 hover:bg-orange-600 text-white text-xs font-medium rounded cursor-grab active:cursor-grabbing transition-all duration-200 hover:shadow-sm max-w-[140px]"
              title={tooltipText}
            >
              <span className="truncate">{displayName}</span>
              <Copy className="h-2.5 w-2.5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
            </div>

            <span className="text-gray-400 text-xs">{typeLabel}</span>
          </div>
        </div>
      );
    }

    // Leaf value rendering
    const displayValue =
      value === null
        ? "null"
        : value === undefined
          ? "undefined"
          : typeof value === "string"
            ? `"${value}"`
            : typeof value === "number"
              ? value.toString()
              : typeof value === "boolean"
                ? value.toString()
                : Array.isArray(value)
                  ? `[]`
                  : JSON.stringify(value);

    // Full value for tooltip (untruncated)
    const fullValueTooltip =
      typeof value === "string" && value.length > 30
        ? value
        : displayValue;

    return (
      <div
        key={key}
        className="flex items-center justify-between ml-2 py-1 px-2 bg-gray-50 rounded hover:bg-gray-100 transition-colors"
      >
        <div className="flex items-center gap-2 flex-1 min-w-0">
          {/* Draggable key badge */}
          <div
            draggable
            onDragStart={(e) => handleDragStart(e, currentPath, value)}
            onClick={() => copyPath(currentPath)}
            className="group inline-flex items-center gap-1 px-2 py-0.5 bg-green-500 hover:bg-green-600 text-white text-xs font-medium rounded cursor-grab active:cursor-grabbing transition-all duration-200 hover:shadow-sm max-w-[140px] flex-shrink-0"
            title={tooltipText}
          >
            <span className="truncate">{displayName}</span>
            <Copy className="h-2.5 w-2.5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
          </div>

          {/* Value with tooltip for long text */}
          <span
            className="text-gray-600 text-xs font-mono truncate cursor-default"
            title={fullValueTooltip}
          >
            {displayValue}
          </span>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-1 max-w-full bg-white">
      {Object.entries(data).map(([key, value]) => {
        const currentPath = basePath ? `${basePath}.${key}` : key;
        return renderValue(key, value, currentPath);
      })}
    </div>
  );
};
