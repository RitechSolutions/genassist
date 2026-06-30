import React, { useState, useRef, useEffect, useContext, createContext } from "react";
import { ChevronDown, ChevronRight, Copy, Check, ChevronsDownUp } from "lucide-react";
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
  level?: number;
}

/**
 * Shared ref to the horizontally-scrollable container, so a node that is
 * expanded deep on the right can scroll itself (and its new children) into view.
 */
const JsonScrollContext = createContext<React.RefObject<HTMLDivElement> | null>(null);

const isComplexValue = (value: JsonValue): boolean =>
  Array.isArray(value) || (typeof value === "object" && value !== null);

/**
 * Renders a single JSON node. Structural lines (keys, brackets, primitives)
 * never wrap — the whole tree grows to its natural width and the outer
 * container scrolls horizontally (DevTools-style). Only long string values
 * wrap, within a bounded width, so one big string can't create endless scroll.
 */
const JsonValue: React.FC<JsonValueProps> = ({ value, level = 0 }) => {
  const [isCollapsed, setIsCollapsed] = useState(level > 2); // Auto-collapse deep levels
  const containerRef = useContext(JsonScrollContext);
  const nodeRef = useRef<HTMLDivElement>(null);
  const mountedRef = useRef(false);

  // When a node is expanded, glide the scroll view so the freshly-opened node
  // (and the children appearing to its right) come into view — instead of
  // leaving the new content off-screen on the right. Skips the initial mount
  // and skips collapses; only nudges nodes that sit in the right half / off-screen.
  useEffect(() => {
    if (!mountedRef.current) {
      mountedRef.current = true;
      return;
    }
    if (isCollapsed) return;

    const container = containerRef?.current;
    const node = nodeRef.current;
    if (!container || !node) return;

    const cRect = container.getBoundingClientRect();
    const nRect = node.getBoundingClientRect();
    const relLeft = nRect.left - cRect.left;

    if (relLeft > cRect.width * 0.5 || relLeft < 0) {
      const target = container.scrollLeft + relLeft - cRect.width * 0.25;
      container.scrollTo({ left: Math.max(0, target), behavior: "smooth" });
    }
  }, [isCollapsed, containerRef]);

  if (value === null) {
    return <span className="text-gray-500">null</span>;
  }

  if (typeof value === "undefined") {
    return <span className="text-gray-500">undefined</span>;
  }

  if (typeof value === "boolean") {
    return <span className="text-blue-600 whitespace-nowrap">{value.toString()}</span>;
  }

  if (typeof value === "number") {
    return <span className="text-green-600 whitespace-nowrap">{value}</span>;
  }

  if (typeof value === "string") {
    return (
      <span className="text-red-600 inline-block max-w-[60ch] whitespace-pre-wrap break-words align-top [overflow-wrap:anywhere]">
        "{value}"
      </span>
    );
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span className="text-gray-500">[]</span>;
    }

    const summary = (
      <span className="whitespace-nowrap">
        <span className="text-gray-500">[</span>
        <span className="text-gray-400"> {value.length} items </span>
        <span className="text-gray-500">]</span>
      </span>
    );

    return (
      <div ref={nodeRef} className="inline-block align-top">
        {/* level 0 has no toggle here — the outer JsonViewer owns the root toggle */}
        {level > 0 ? (
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="inline-flex items-center gap-1 text-gray-600 hover:text-gray-800 align-top"
          >
            {isCollapsed ? <ChevronRight className="h-3 w-3 shrink-0" /> : <ChevronDown className="h-3 w-3 shrink-0" />}
            {summary}
          </button>
        ) : (
          summary
        )}

        {!isCollapsed && (
          <div className="ml-3 mt-1 space-y-1 border-l border-gray-200 pl-3">
            {value.map((item, index) => (
              <div key={index} className="flex items-start gap-1.5">
                <span className="text-gray-400 text-xs whitespace-nowrap pt-px">{index}:</span>
                <JsonValue value={item} level={level + 1} />
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

    const summary = (
      <span className="whitespace-nowrap">
        <span className="text-gray-500">{"{"}</span>
        <span className="text-gray-400"> {keys.length} properties </span>
        <span className="text-gray-500">{"}"}</span>
      </span>
    );

    return (
      <div ref={nodeRef} className="inline-block align-top">
        {/* level 0 has no toggle here — the outer JsonViewer owns the root toggle */}
        {level > 0 ? (
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="inline-flex items-center gap-1 text-gray-600 hover:text-gray-800 align-top"
          >
            {isCollapsed ? <ChevronRight className="h-3 w-3 shrink-0" /> : <ChevronDown className="h-3 w-3 shrink-0" />}
            {summary}
          </button>
        ) : (
          summary
        )}

        {!isCollapsed && (
          <div className="ml-3 mt-1 space-y-1 border-l border-gray-200 pl-3">
            {keys.map((key) => (
              <div key={key} className="flex items-start gap-1.5">
                <span className="text-blue-600 font-medium whitespace-nowrap pt-px">"{key}":</span>
                <JsonValue value={value[key]} level={level + 1} />
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  return <span className="text-gray-600">{String(value)}</span>;
};

const JsonViewer: React.FC<JsonViewerProps> = ({ data, name, level = 0, collapsed = false, onCopy }) => {
  const [isCollapsed, setIsCollapsed] = useState(collapsed);
  const [copied, setCopied] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  // Remount key — bumping it resets every node's collapse state back to its
  // default (deep levels auto-collapsed), i.e. "collapse all to default".
  const [resetKey, setResetKey] = useState(0);

  const handleCollapseAll = () => {
    setResetKey((k) => k + 1);
    containerRef.current?.scrollTo({ left: 0 });
  };

  const handleCopy = () => {
    const jsonString = JSON.stringify(data, null, 2);
    navigator.clipboard.writeText(jsonString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    if (onCopy) {
      onCopy(data);
    }
  };

  const isComplex = isComplexValue(data);

  return (
    <div className="font-mono text-sm">
      {(name || onCopy) && (
        <div className="flex items-center justify-between mb-2">
          {name ? <span className="text-gray-700 font-medium">{name}</span> : <span />}
          <div className="flex items-center gap-1">
            {isComplex && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleCollapseAll}
                className="h-6 px-2 text-xs flex-shrink-0"
                title="Collapse all to default"
              >
                <ChevronsDownUp className="h-3 w-3 mr-1" /> Collapse all
              </Button>
            )}
            {onCopy && (
              <Button variant="ghost" size="sm" onClick={handleCopy} className="h-6 px-2 text-xs flex-shrink-0">
                {copied ? (
                  <>
                    <Check className="h-3 w-3 text-green-600 mr-1" /> Copied
                  </>
                ) : (
                  <>
                    <Copy className="h-3 w-3 mr-1" /> Copy
                  </>
                )}
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Own only horizontal scroll; let the surrounding container handle
          vertical scroll so we never nest two vertical scrollbars. */}
      <div ref={containerRef} className="bg-gray-50 border border-gray-200 rounded-md p-3 overflow-x-auto">
        {/* min-w-max makes width content-driven so the tree scrolls
            horizontally instead of squeezing deep nodes into thin columns */}
        <JsonScrollContext.Provider value={containerRef}>
          <div className="min-w-max">
            {isComplex ? (
              <div className="flex items-start gap-1.5">
                <button
                  onClick={() => setIsCollapsed(!isCollapsed)}
                  className="flex items-center gap-1 text-gray-600 hover:text-gray-800 flex-shrink-0 pt-px"
                >
                  {isCollapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                </button>
                <div>
                  {!isCollapsed ? (
                    <JsonValue key={resetKey} value={data} level={level} />
                  ) : (
                    <span className="text-gray-400">
                      {Array.isArray(data) ? `[${data.length} items]` : `{${Object.keys(data).length} properties}`}
                    </span>
                  )}
                </div>
              </div>
            ) : (
              <JsonValue value={data} level={level} />
            )}
          </div>
        </JsonScrollContext.Provider>
      </div>
    </div>
  );
};

export default JsonViewer;
