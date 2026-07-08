import React, { useEffect, useState } from "react";
import { WebScraperNodeData } from "../types/nodes";
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
import { Plus, X, Save } from "lucide-react";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { DraggableInput } from "../components/custom/DraggableInput";

const OUTPUT_FORMATS = ["markdown", "html", "both"] as const;
type OutputFormat = (typeof OUTPUT_FORMATS)[number];

const SCREENSHOT_MODES = ["off", "viewport", "fullPage"] as const;
type ScreenshotMode = (typeof SCREENSHOT_MODES)[number];

export const WebScraperDialog: React.FC<
  BaseNodeDialogProps<WebScraperNodeData, WebScraperNodeData>
> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const [name, setName] = useState(data.name || "");
  const [url, setUrl] = useState(data.url || "");
  const [format, setFormat] = useState<OutputFormat>(
    (data.format as OutputFormat) || "markdown"
  );
  const [renderJs, setRenderJs] = useState<boolean>(data.renderJs ?? false);
  const [onlyMainContent, setOnlyMainContent] = useState<boolean>(
    data.onlyMainContent ?? true
  );
  const [includeLinks, setIncludeLinks] = useState<boolean>(
    data.includeLinks ?? true
  );
  const [includeMetadata, setIncludeMetadata] = useState<boolean>(
    data.includeMetadata ?? true
  );
  const [screenshot, setScreenshot] = useState<ScreenshotMode>(
    (data.screenshot as ScreenshotMode) || "off"
  );
  const [headers, setHeaders] = useState<Record<string, string>>(
    data.headers || {}
  );
  useEffect(() => {
    setName(data.name || "");
    setUrl(data.url || "");
    setFormat((data.format as OutputFormat) || "markdown");
    setRenderJs(data.renderJs ?? false);
    setOnlyMainContent(data.onlyMainContent ?? true);
    setIncludeLinks(data.includeLinks ?? true);
    setIncludeMetadata(data.includeMetadata ?? true);
    setScreenshot((data.screenshot as ScreenshotMode) || "off");
    setHeaders(data.headers || {});
  }, [isOpen]);

  const handleSave = () => {
    onUpdate({
      ...data,
      name,
      url,
      format,
      renderJs,
      onlyMainContent,
      includeLinks,
      includeMetadata,
      screenshot,
      headers,
    });
    onClose();
  };

  const addHeader = () => {
    setHeaders({ ...headers, "": "" });
  };

  const updateHeader = (oldKey: string, newKey: string, value: string) => {
    const newHeaders: Record<string, string> = {};

    // Iterate through existing headers to maintain order
    for (const [key, val] of Object.entries(headers)) {
      if (key === oldKey) {
        // Update the header with new key and value
        newHeaders[newKey] = value;
      } else {
        // Keep other headers as they were
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
        renderJs,
        onlyMainContent,
        includeLinks,
        includeMetadata,
        screenshot,
        headers,
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
          onValueChange={(value) => setFormat(value as OutputFormat)}
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
          onValueChange={(value) => setScreenshot(value as ScreenshotMode)}
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
          Capturing a screenshot forces the slower headless-browser path.
        </div>
      </div>

      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <Label>Render JavaScript</Label>
          <p className="text-xs text-muted-foreground">
            Loads the page in a headless browser for JS-heavy sites. Slower than
            the default fast fetch.
          </p>
        </div>
        <Switch checked={renderJs} onCheckedChange={setRenderJs} />
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

      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <Label>Include Links</Label>
          <p className="text-xs text-muted-foreground">
            Returns a links[] array of the absolute URLs found on the page.
          </p>
        </div>
        <Switch checked={includeLinks} onCheckedChange={setIncludeLinks} />
      </div>

      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <Label>Include Metadata</Label>
          <p className="text-xs text-muted-foreground">
            Returns a metadata object with the page title, description, Open
            Graph tags and canonical URL.
          </p>
        </div>
        <Switch
          checked={includeMetadata}
          onCheckedChange={setIncludeMetadata}
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
    </NodeConfigPanel>
  );
};
