import React, { useState } from "react";
import { ChevronDown, ChevronRight, Copy, Check } from "lucide-react";
import { Button } from "@/components/button";

type JsonValue = string | number | boolean | null | JsonObject | JsonArray;
type JsonObject = { [key: string]: JsonValue };
type JsonArray = JsonValue[];

interface JsonViewerProps {
  data: JsonValue;
  name?: string;
  level?: number;
  collapsed?: boolean;
  onCopy?: (data: JsonValue) => void;
}

interface JsonValueProps {
  value: JsonValue;
  key?: string;
  level?: number;
}

const JsonValue: React.FC<JsonValueProps> = ({ value, key, level = 0 }) => {
  const [isCollapsed, setIsCollapsed] = useState(level > 2); // Auto-collapse deep levels

  if (value === null) {
    return <span className="text-gray-500">null</span>;
  }
  
  if (typeof value === "undefined") {
    return <span className="text-gray-500">undefined</span>;
  }
  
  if (typeof value === "boolean") {
    return <span className="text-blue-600">{value.toString()}</span>;
  }
  
  if (typeof value === "number") {
    return <span className="text-green-600">{value}</span>;
  }
  
  if (typeof value === "string") {
    return <span className="text-red-600">"{value}"</span>;
  }
  
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span className="text-gray-500">[]</span>;
    }
    
    return (
      <div className={level > 0 ? "ml-2" : ""}>
        <div className="flex items-center gap-2">
          {level > 0 && (
            <button
              onClick={() => setIsCollapsed(!isCollapsed)}
              className="flex items-center gap-1 text-gray-600 hover:text-gray-800"
            >
              {isCollapsed ? (
                <ChevronRight className="h-3 w-3" />
              ) : (
                <ChevronDown className="h-3 w-3" />
              )}
            </button>
          )}
          <span className="text-gray-500">[</span>
          <span className="text-gray-400">{value.length} items</span>
          <span className="text-gray-500">]</span>
        </div>
        
        {!isCollapsed && (
          <div className="ml-4 space-y-1 mt-1">
            {value.map((item, index) => (
              <div key={index} className="flex items-start gap-2">
                <span className="text-gray-400 text-sm">{index}:</span>
                <div className="flex-1">
                  <JsonValue value={item} level={level + 1} />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }
  
  if (typeof value === "object") {
    const keys = Object.keys(value);
    if (keys.length === 0) {
      return <span className="text-gray-500">{"{}"}</span>;
    }
    
    return (
      <div className={level > 0 ? "ml-2" : ""}>
        <div className="flex items-center gap-2">
          {level > 0 && (
            <button
              onClick={() => setIsCollapsed(!isCollapsed)}
              className="flex items-center gap-1 text-gray-600 hover:text-gray-800"
            >
              {isCollapsed ? (
                <ChevronRight className="h-3 w-3" />
              ) : (
                <ChevronDown className="h-3 w-3" />
              )}
            </button>
          )}
          <span className="text-gray-500">{"{"}</span>
          <span className="text-gray-400">{keys.length} properties</span>
          <span className="text-gray-500">{"}"}</span>
        </div>
        
        {!isCollapsed && (
          <div className="ml-4 space-y-1 mt-1">
            {keys.map((key) => (
              <div key={key} className="flex items-start gap-2">
                <span className="text-blue-600 font-medium">"{key}":</span>
                <div className="flex-1">
                  <JsonValue value={value[key]} level={level + 1} />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }
  
  return <span className="text-gray-600">{String(value)}</span>;
};

const JsonViewer: React.FC<JsonViewerProps> = ({
  data,
  name,
  level = 0,
  collapsed = false,
  onCopy,
}) => {
  const [isCollapsed, setIsCollapsed] = useState(collapsed);
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    const jsonString = JSON.stringify(data, null, 2);
    navigator.clipboard.writeText(jsonString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    if (onCopy) {
      onCopy(data);
    }
  };

  const isComplex = (value: JsonValue): boolean => {
    return (
      (typeof value === "object" && value !== null) ||
      Array.isArray(value)
    );
  };

  return (
    <div className="font-mono text-sm">
      {name && (
        <div className="flex items-center justify-between mb-2">
          <span className="text-gray-700 font-medium">{name}</span>
          {onCopy && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCopy}
              className="h-6 px-2 text-xs"
            >
              {copied ? (
                <Check className="h-3 w-3 text-green-600" />
              ) : (
                <Copy className="h-3 w-3" />
              )}
            </Button>
          )}
        </div>
      )}
      
      <div className="bg-gray-50 border border-gray-200 rounded-md p-3 overflow-x-auto">
        {isComplex(data) ? (
          <div className="flex items-start gap-2">
            <button
              onClick={() => setIsCollapsed(!isCollapsed)}
              className="flex items-center gap-1 text-gray-600 hover:text-gray-800 flex-shrink-0"
            >
              {isCollapsed ? (
                <ChevronRight className="h-3 w-3" />
              ) : (
                <ChevronDown className="h-3 w-3" />
              )}
            </button>
            <div className="flex-1 min-w-0">
              {!isCollapsed && <JsonValue value={data} level={level} />}
              {isCollapsed && (
                <span className="text-gray-400">
                  {Array.isArray(data) ? `[${data.length} items]` : `{${Object.keys(data).length} properties}`}
                </span>
              )}
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <div className="flex-1"><JsonValue value={data} level={level} /></div>
            {onCopy && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleCopy}
                className="h-6 px-2 text-xs flex-shrink-0"
              >
                {copied ? (
                  <Check className="h-3 w-3 text-green-600" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default JsonViewer;
