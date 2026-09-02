import React, { useEffect, useState } from "react";
import {
  WebScraperNodeData,
  WebScraperFormat,
  WebScraperScreenshot,
} from "../types/nodes";
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
import { Switch } from "@/components/switch";
import { Plus, X, Save, ChevronDown, ChevronUp } from "lucide-react";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { DraggableInput } from "../components/custom/DraggableInput";
import { useNodeDialogState } from "./useNodeDialogState";

// open the advanced section when any advanced option is set away from its default
const hasAdvancedOptions = (data: WebScraperNodeData): boolean =>
  Boolean(data.waitFor || data.scrollToBottom || data.maxAge);

export const WebScraperDialog: React.FC<
  BaseNodeDialogProps<WebScraperNodeData, WebScraperNodeData>
> = (props) => {
  const { isOpen, onClose, data } = props;

  const { values, setField, merged, handleSave } = useNodeDialogState(
    props,
    () => ({
      name: data.name || "",
      url: data.url || "",
      format: data.format || "markdown",
      onlyMainContent: data.onlyMainContent ?? true,
      screenshot: data.screenshot || "off",
      headers: data.headers || {},
      waitFor: data.waitFor ?? 0,
      scrollToBottom: data.scrollToBottom ?? false,
      maxAge: data.maxAge ?? 0,
    })
  );

  const [showAdvanced, setShowAdvanced] = useState(hasAdvancedOptions(data));
  useEffect(() => {
    if (isOpen) {
      setShowAdvanced(hasAdvancedOptions(data));
    }
  }, [isOpen, data]);

  const addHeader = () => {
    setField("headers", { ...values.headers, "": "" });
  };

  const updateHeader = (oldKey: string, newKey: string, value: string) => {
    const newHeaders: Record<string, string> = {};
    for (const [key, val] of Object.entries(values.headers)) {
      if (key === oldKey) {
        newHeaders[newKey] = value;
      } else {
        newHeaders[key] = val;
      }
    }
    setField("headers", newHeaders);
  };

  const removeHeader = (key: string) => {
    const newHeaders = { ...values.headers };
    delete newHeaders[key];
    setField("headers", newHeaders);
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
      data={merged}
    >
      <div className="space-y-2">
        <Label htmlFor="name">Name</Label>
        <RichInput
          id="name"
          value={values.name}
          onChange={(e) => setField("name", e.target.value)}
          placeholder="Web Scraper"
          className="break-all w-full"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="url">URL</Label>
        <DraggableInput
          id="url"
          value={values.url}
          onChange={(e) => setField("url", e.target.value)}
          placeholder="https://example.com"
          className="break-all w-full"
        />
        <div className="text-xs text-muted-foreground break-words">
          Use {"{{field}}"} to define dynamic parameters
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="format">Output Format</Label>
        <Select
          value={values.format}
          onValueChange={(value) =>
            setField("format", value as WebScraperFormat)
          }
        >
          <SelectTrigger>
            <SelectValue placeholder="Select output format" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="markdown">Markdown</SelectItem>
            <SelectItem value="html">HTML</SelectItem>
            <SelectItem value="both">Both</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="screenshot">Screenshot</Label>
        <Select
          value={values.screenshot}
          onValueChange={(value) =>
            setField("screenshot", value as WebScraperScreenshot)
          }
        >
          <SelectTrigger>
            <SelectValue placeholder="Select screenshot mode" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="off">Off</SelectItem>
            <SelectItem value="viewport">Viewport</SelectItem>
            <SelectItem value="fullPage">Full Page</SelectItem>
          </SelectContent>
        </Select>
        <div className="text-xs text-muted-foreground break-words">
          Capture a viewport or full-page screenshot of the rendered page.
        </div>
      </div>

      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <Label>Only Main Content</Label>
          <p className="text-xs text-muted-foreground">
            Extracts the primary article and drops nav, ads and boilerplate.
            Falls back to the full page when extraction is too thin.
          </p>
        </div>
        <Switch
          checked={values.onlyMainContent}
          onCheckedChange={(checked) => setField("onlyMainContent", checked)}
        />
      </div>

      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <Label>Headers</Label>
          <Button
            size="sm"
            variant="outline"
            className="h-6 text-xs"
            onClick={addHeader}
          >
            <Plus className="h-3 w-3 mr-1" /> Add Header
          </Button>
        </div>

        <div className="space-y-2">
          {Object.entries(values.headers).map(([key, value], idx) => (
            <div
              key={`header-${idx}`}
              className="flex items-center gap-2 w-full"
            >
              <DraggableInput
                placeholder="Header name"
                value={key}
                onChange={(e) => updateHeader(key, e.target.value, value)}
                className="flex-1 text-xs min-w-0 w-full"
              />
              <DraggableInput
                placeholder="Value"
                value={value}
                onChange={(e) => updateHeader(key, key, e.target.value)}
                className="flex-1 text-xs min-w-0 w-full"
              />
              <Button
                size="icon"
                variant="ghost"
                className="h-6 w-6 flex-shrink-0"
                onClick={() => removeHeader(key)}
              >
                <X className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))}
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
              <Label htmlFor="waitFor">Wait For (ms)</Label>
              <RichInput
                id="waitFor"
                type="number"
                value={String(values.waitFor)}
                onChange={(e) =>
                  setField("waitFor", Math.max(0, parseInt(e.target.value) || 0))
                }
                placeholder="0"
                className="w-full"
              />
              <div className="text-xs text-muted-foreground break-words">
                Extra wait after load before capturing, for slow
                client-rendered pages.
              </div>
            </div>

            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <Label>Scroll To Bottom</Label>
                <p className="text-xs text-muted-foreground">
                  Scrolls the page to trigger lazy-loaded content before
                  scraping.
                </p>
              </div>
              <Switch
                checked={values.scrollToBottom}
                onCheckedChange={(checked) =>
                  setField("scrollToBottom", checked)
                }
              />
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
                placeholder="0"
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
