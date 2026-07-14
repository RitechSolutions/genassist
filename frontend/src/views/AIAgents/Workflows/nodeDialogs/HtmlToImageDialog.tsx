import React, { useEffect, useState } from "react";
import {
  HtmlToImageNodeData,
  HtmlToImageCaptureMode,
} from "../types/nodes";
import { Button } from "@/components/button";
import { RichInput } from "@/components/richInput";
import { RichTextarea } from "@/components/richTextarea";
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

// open the advanced section when any advanced option is set away from its default
const hasAdvancedOptions = (data: HtmlToImageNodeData): boolean =>
  Boolean(data.waitFor);

export const HtmlToImageDialog: React.FC<
  BaseNodeDialogProps<HtmlToImageNodeData, HtmlToImageNodeData>
> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const [name, setName] = useState(data.name || "");
  const [html, setHtml] = useState(data.html || "");
  const [captureMode, setCaptureMode] = useState<HtmlToImageCaptureMode>(
    data.captureMode || "fullPage"
  );
  const [viewportWidth, setViewportWidth] = useState<number>(
    data.viewportWidth ?? 1280
  );
  const [viewportHeight, setViewportHeight] = useState<number>(
    data.viewportHeight ?? 720
  );
  const [waitFor, setWaitFor] = useState<number>(data.waitFor ?? 0);
  const [showAdvanced, setShowAdvanced] = useState(hasAdvancedOptions(data));

  useEffect(() => {
    setName(data.name || "");
    setHtml(data.html || "");
    setCaptureMode(data.captureMode || "fullPage");
    setViewportWidth(data.viewportWidth ?? 1280);
    setViewportHeight(data.viewportHeight ?? 720);
    setWaitFor(data.waitFor ?? 0);
    setShowAdvanced(hasAdvancedOptions(data));
  }, [isOpen]);

  const handleSave = () => {
    onUpdate({
      ...data,
      name,
      html,
      captureMode,
      viewportWidth,
      viewportHeight,
      waitFor,
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
        html,
        captureMode,
        viewportWidth,
        viewportHeight,
        waitFor,
      }}
    >
      <div className="space-y-2">
        <Label htmlFor="name">Name</Label>
        <RichInput
          id="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="HTML to Image"
          className="break-all w-full"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="html">HTML</Label>
        <RichTextarea
          id="html"
          value={html}
          onChange={(e) => setHtml(e.target.value)}
          placeholder="<html>...</html>"
          className="w-full min-h-[160px] font-mono"
        />
        <div className="text-xs text-gray-500 break-words">
          The HTML to render. Use {"{{field}}"} to define dynamic parameters. An
          upstream input overrides this value.
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="captureMode">Capture Mode</Label>
        <Select
          value={captureMode}
          onValueChange={(value) =>
            setCaptureMode(value as HtmlToImageCaptureMode)
          }
        >
          <SelectTrigger>
            <SelectValue placeholder="Select capture mode" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="fullPage">Full Page</SelectItem>
            <SelectItem value="viewport">Viewport</SelectItem>
          </SelectContent>
        </Select>
        <div className="text-xs text-gray-500 break-words">
          Full Page captures the entire rendered content; Viewport captures only
          the configured viewport area.
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="viewportWidth">Viewport Width (px)</Label>
        <RichInput
          id="viewportWidth"
          type="number"
          value={String(viewportWidth)}
          onChange={(e) =>
            setViewportWidth(Math.max(1, parseInt(e.target.value) || 0))
          }
          placeholder="1280"
          className="w-full"
        />
      </div>

      {captureMode === "viewport" && (
        <div className="space-y-2">
          <Label htmlFor="viewportHeight">Viewport Height (px)</Label>
          <RichInput
            id="viewportHeight"
            type="number"
            value={String(viewportHeight)}
            onChange={(e) =>
              setViewportHeight(Math.max(1, parseInt(e.target.value) || 0))
            }
            placeholder="720"
            className="w-full"
          />
        </div>
      )}

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
                Extra wait after render before capturing, for slow
                client-rendered content.
              </div>
            </div>
          </div>
        )}
      </div>
    </NodeConfigPanel>
  );
};
