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

// open the advanced section when any advanced option is set away from its default
const hasAdvancedOptions = (data: WebScraperNodeData): boolean =>
  Boolean(data.waitFor || data.scrollToBottom || data.maxAge);

export const WebScraperDialog: React.FC<
  BaseNodeDialogProps<WebScraperNodeData, WebScraperNodeData>
> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const [name, setName] = useState(data.name || "");
  const [url, setUrl] = useState(data.url || "");
  const [format, setFormat] = useState<WebScraperFormat>(
    data.format || "markdown"
  );
  const [onlyMainContent, setOnlyMainContent] = useState<boolean>(
    data.onlyMainContent ?? true
  );
  const [screenshot, setScreenshot] = useState<WebScraperScreenshot>(
    data.screenshot || "off"
  );
  const [headers, setHeaders] = useState<Record<string, string>>(
    data.headers || {}
  );
  const [waitFor, setWaitFor] = useState<number>(data.waitFor ?? 0);
  const [scrollToBottom, setScrollToBottom] = useState<boolean>(
    data.scrollToBottom ?? false
  );
  const [maxAge, setMaxAge] = useState<number>(data.maxAge ?? 0);
  const [showAdvanced, setShowAdvanced] = useState(hasAdvancedOptions(data));
  useEffect(() => {
    setName(data.name || "");
    setUrl(data.url || "");
    setFormat(data.format || "markdown");
    setOnlyMainContent(data.onlyMainContent ?? true);
    setScreenshot(data.screenshot || "off");
    setHeaders(data.headers || {});
    setWaitFor(data.waitFor ?? 0);
    setScrollToBottom(data.scrollToBottom ?? false);
    setMaxAge(data.maxAge ?? 0);
    setShowAdvanced(hasAdvancedOptions(data));
  }, [isOpen]);

  const handleSave = () => {
    onUpdate({
      ...data,
      name,
      url,
      format,
      onlyMainContent,
      screenshot,
      headers,
      waitFor,
      scrollToBottom,
      maxAge,
    });
    onClose();
  };

  const addHeader = () => {
    setHeaders({ ...headers, "": "" });
  };

  const updateHeader = (oldKey: string, newKey: string, value: string) => {
    const newHeaders: Record<string, string> = {};
    for (const [key, val] of Object.entries(headers)) {
      if (key === oldKey) {
        newHeaders[newKey] = value;
      } else {
        newHeaders[key] = val;
      }
    }
    setHeaders(newHeaders);
  };

  const removeHeader = (key: string) => {
    const newHeaders = { ...headers };
    delete newHeaders[key];
    setHeaders(newHeaders);
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
        url,
        format,
        onlyMainContent,
        screenshot,
        headers,
        waitFor,
        scrollToBottom,
        maxAge,
      }}
    >
      <div className="space-y-2">
        <Label htmlFor="name">Name</Label>
        <RichInput
          id="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Web Scraper"
          className="break-all w-full"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="url">URL</Label>
        <DraggableInput
          id="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.com"
          className="break-all w-full"
        />
        <div className="text-xs text-gray-500 break-words">
          Use {"{{field}}"} to define dynamic parameters
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="format">Output Format</Label>
        <Select
          value={format}
          onValueChange={(value) => setFormat(value as WebScraperFormat)}
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
          value={screenshot}
          onValueChange={(value) => setScreenshot(value as WebScraperScreenshot)}
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
        <div className="text-xs text-gray-500 break-words">
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
          checked={onlyMainContent}
          onCheckedChange={setOnlyMainContent}
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
          {Object.entries(headers).map(([key, value], idx) => (
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
              <Label htmlFor="waitFor">Wait For (ms)</Label>
              <RichInput
                id="waitFor"
                type="number"
                value={String(waitFor)}
                onChange={(e) =>
                  setWaitFor(Math.max(0, parseInt(e.target.value) || 0))
                }
                placeholder="0"
                className="w-full"
              />
              <div className="text-xs text-gray-500 break-words">
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
                checked={scrollToBottom}
                onCheckedChange={setScrollToBottom}
              />
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
                placeholder="0"
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
