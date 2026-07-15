import React, { useEffect, useState } from "react";
import { WebSearchNodeData, WebSearchDepth } from "../types/nodes";
import { Button } from "@/components/button";
import { RichInput } from "@/components/richInput";
import { Label } from "@/components/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Save, ChevronDown, ChevronUp } from "lucide-react";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { DraggableInput } from "../components/custom/DraggableInput";

// open the advanced section when any advanced option differs from its default
const hasAdvancedOptions = (data: WebSearchNodeData): boolean =>
  Boolean(data.includeDomains) ||
  Boolean(data.excludeDomains) ||
  (data.maxContentChars ?? 2000) !== 2000 ||
  (data.maxTotalContentChars ?? 8000) !== 8000 ||
  (data.maxAge ?? 600) !== 600;

export const WebSearchDialog: React.FC<
  BaseNodeDialogProps<WebSearchNodeData, WebSearchNodeData>
> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const [name, setName] = useState(data.name || "");
  const [query, setQuery] = useState(data.query || "");
  const [maxResults, setMaxResults] = useState<number>(data.maxResults ?? 5);
  const [searchDepth, setSearchDepth] = useState<WebSearchDepth>(
    data.searchDepth || "basic"
  );
  const [includeDomains, setIncludeDomains] = useState(
    data.includeDomains || ""
  );
  const [excludeDomains, setExcludeDomains] = useState(
    data.excludeDomains || ""
  );
  const [maxContentChars, setMaxContentChars] = useState<number>(
    data.maxContentChars ?? 2000
  );
  const [maxTotalContentChars, setMaxTotalContentChars] = useState<number>(
    data.maxTotalContentChars ?? 8000
  );
  const [maxAge, setMaxAge] = useState<number>(data.maxAge ?? 600);
  const [showAdvanced, setShowAdvanced] = useState(hasAdvancedOptions(data));
  useEffect(() => {
    setName(data.name || "");
    setQuery(data.query || "");
    setMaxResults(data.maxResults ?? 5);
    setSearchDepth(data.searchDepth || "basic");
    setIncludeDomains(data.includeDomains || "");
    setExcludeDomains(data.excludeDomains || "");
    setMaxContentChars(data.maxContentChars ?? 2000);
    setMaxTotalContentChars(data.maxTotalContentChars ?? 8000);
    setMaxAge(data.maxAge ?? 600);
    setShowAdvanced(hasAdvancedOptions(data));
  }, [isOpen]);

  const handleSave = () => {
    onUpdate({
      ...data,
      name,
      query,
      maxResults,
      searchDepth,
      includeDomains,
      excludeDomains,
      maxContentChars,
      maxTotalContentChars,
      maxAge,
    });
    onClose();
  };

  return (
    <NodeConfigPanel
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave}>
            <Save className="h-4 w-4 mr-2" />
            Save Changes
          </Button>
        </>
      }
      {...props}
      data={{
        ...data,
        name,
        query,
        maxResults,
        searchDepth,
        includeDomains,
        excludeDomains,
        maxContentChars,
        maxTotalContentChars,
        maxAge,
      }}
    >
      <div className="space-y-2">
        <Label htmlFor="name">Name</Label>
        <RichInput
          id="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Web Search"
          className="break-all w-full"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="query">Query</Label>
        <DraggableInput
          id="query"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search the web for..."
          className="break-all w-full"
        />
        <div className="text-xs text-gray-500 break-words">
          Use {"{{field}}"} to define dynamic parameters
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="maxResults">Max Results</Label>
        <RichInput
          id="maxResults"
          type="number"
          value={String(maxResults)}
          onChange={(e) =>
            setMaxResults(Math.max(1, parseInt(e.target.value) || 1))
          }
          placeholder="5"
          className="w-full"
        />
        <div className="text-xs text-gray-500 break-words">
          Upper bound (up to 20); filtering may return fewer.
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="searchDepth">Search Depth</Label>
        <Select
          value={searchDepth}
          onValueChange={(value) => setSearchDepth(value as WebSearchDepth)}
        >
          <SelectTrigger>
            <SelectValue placeholder="Select search depth" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="basic">Basic</SelectItem>
            <SelectItem value="advanced">Advanced</SelectItem>
          </SelectContent>
        </Select>
        <div className="text-xs text-gray-500 break-words">
          Advanced fetches page content from the top results within a total
          budget.
        </div>
      </div>

      <div className="space-y-2">
        <button
          type="button"
          className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700"
          onClick={() => setShowAdvanced((v) => !v)}
        >
          {showAdvanced ? (
            <ChevronUp className="h-3 w-3" />
          ) : (
            <ChevronDown className="h-3 w-3" />
          )}
          Advanced
        </button>

        {showAdvanced && (
          <div className="space-y-4 pt-2">
            <div className="space-y-2">
              <Label htmlFor="includeDomains">Include Domain</Label>
              <DraggableInput
                id="includeDomains"
                value={includeDomains}
                onChange={(e) => setIncludeDomains(e.target.value)}
                placeholder="example.com"
                className="break-all w-full"
              />
              <div className="text-xs text-gray-500 break-words">
                Restrict results to one domain (v1).
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="excludeDomains">Exclude Domains</Label>
              <DraggableInput
                id="excludeDomains"
                value={excludeDomains}
                onChange={(e) => setExcludeDomains(e.target.value)}
                placeholder="reddit.com, pinterest.com"
                className="break-all w-full"
              />
              <div className="text-xs text-gray-500 break-words">
                Comma-separated, up to 10 domains.
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="maxContentChars">
                Max Content Chars (per result)
              </Label>
              <RichInput
                id="maxContentChars"
                type="number"
                value={String(maxContentChars)}
                onChange={(e) =>
                  setMaxContentChars(Math.max(0, parseInt(e.target.value) || 0))
                }
                placeholder="2000"
                className="w-full"
              />
              <div className="text-xs text-gray-500 break-words">
                Per-result content cap in advanced depth.
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="maxTotalContentChars">
                Max Total Content Chars
              </Label>
              <RichInput
                id="maxTotalContentChars"
                type="number"
                value={String(maxTotalContentChars)}
                onChange={(e) =>
                  setMaxTotalContentChars(
                    Math.max(0, parseInt(e.target.value) || 0)
                  )
                }
                placeholder="8000"
                className="w-full"
              />
              <div className="text-xs text-gray-500 break-words">
                Total enrichment budget across results in advanced depth.
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="maxAge">Cache Max Age (seconds)</Label>
              <RichInput
                id="maxAge"
                type="number"
                value={String(maxAge)}
                onChange={(e) =>
                  setMaxAge(Math.max(0, parseInt(e.target.value) || 0))
                }
                placeholder="600"
                className="w-full"
              />
              <div className="text-xs text-gray-500 break-words">
                Serve a cached result newer than this. 0 disables caching.
              </div>
            </div>
          </div>
        )}
      </div>
    </NodeConfigPanel>
  );
};
