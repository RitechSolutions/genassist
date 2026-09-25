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
import { DraggableTextArea } from "../components/custom/DraggableTextArea";
import { useNodeDialogState } from "./useNodeDialogState";

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
  const { isOpen, onClose, data } = props;

  const { values, setField, merged, handleSave } = useNodeDialogState(
    props,
    () => ({
      name: data.name || "",
      query: data.query || "",
      maxResults: data.maxResults ?? 5,
      searchDepth: data.searchDepth || "basic",
      includeDomains: data.includeDomains || "",
      excludeDomains: data.excludeDomains || "",
      maxContentChars: data.maxContentChars ?? 2000,
      maxTotalContentChars: data.maxTotalContentChars ?? 8000,
      maxAge: data.maxAge ?? 600,
    })
  );

  const [showAdvanced, setShowAdvanced] = useState(hasAdvancedOptions(data));
  useEffect(() => {
    if (isOpen) {
      setShowAdvanced(hasAdvancedOptions(data));
    }
  }, [isOpen, data]);

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
      data={merged}
    >
      <div className="space-y-2">
        <Label htmlFor="name">Name</Label>
        <RichInput
          id="name"
          value={values.name}
          onChange={(e) => setField("name", e.target.value)}
          placeholder="Web Search"
          className="break-all w-full"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="query">Query</Label>
        <DraggableInput
          id="query"
          value={values.query}
          onChange={(e) => setField("query", e.target.value)}
          placeholder="Search the web for..."
          className="break-all w-full"
        />
        <div className="text-xs text-muted-foreground break-words">
          Use {"{{field}}"} to define dynamic parameters
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="maxResults">Max Results</Label>
        <RichInput
          id="maxResults"
          type="number"
          value={String(values.maxResults)}
          onChange={(e) =>
            setField("maxResults", Math.max(1, parseInt(e.target.value) || 1))
          }
          placeholder="5"
          className="w-full"
        />
        <div className="text-xs text-muted-foreground break-words">
          Upper bound (up to 20); filtering may return fewer.
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="searchDepth">Search Depth</Label>
        <Select
          value={values.searchDepth}
          onValueChange={(value) =>
            setField("searchDepth", value as WebSearchDepth)
          }
        >
          <SelectTrigger>
            <SelectValue placeholder="Select search depth" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="basic">Basic</SelectItem>
            <SelectItem value="advanced">Advanced</SelectItem>
          </SelectContent>
        </Select>
        <div className="text-xs text-muted-foreground break-words">
          Advanced fetches the most query-relevant page content from the top
          results within a total budget.
        </div>
      </div>

      <div className="space-y-2">
        <button
          type="button"
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-muted-foreground"
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
                value={values.includeDomains}
                onChange={(e) => setField("includeDomains", e.target.value)}
                placeholder="example.com"
                className="break-all w-full"
              />
              <div className="text-xs text-muted-foreground break-words">
                Restrict results to one domain.
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="excludeDomains">Exclude Domains</Label>
              <DraggableTextArea
                id="excludeDomains"
                size="hint"
                value={values.excludeDomains}
                onChange={(e) => setField("excludeDomains", e.target.value)}
                placeholder="reddit.com, pinterest.com"
                className="w-full text-sm"
              />
              <div className="text-xs text-muted-foreground break-words">
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
                value={String(values.maxContentChars)}
                onChange={(e) =>
                  setField(
                    "maxContentChars",
                    Math.max(0, parseInt(e.target.value) || 0)
                  )
                }
                placeholder="2000"
                className="w-full"
              />
              <div className="text-xs text-muted-foreground break-words">
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
                value={String(values.maxTotalContentChars)}
                onChange={(e) =>
                  setField(
                    "maxTotalContentChars",
                    Math.max(0, parseInt(e.target.value) || 0)
                  )
                }
                placeholder="8000"
                className="w-full"
              />
              <div className="text-xs text-muted-foreground break-words">
                Total enrichment budget across results in advanced depth.
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="maxAge">Cache Max Age (seconds)</Label>
              <RichInput
                id="maxAge"
                type="number"
                value={String(values.maxAge)}
                onChange={(e) =>
                  setField("maxAge", Math.max(0, parseInt(e.target.value) || 0))
                }
                placeholder="600"
                className="w-full"
              />
              <div className="text-xs text-muted-foreground break-words">
                Serve a cached result newer than this. 0 disables caching.
              </div>
            </div>
          </div>
        )}
      </div>
    </NodeConfigPanel>
  );
};
