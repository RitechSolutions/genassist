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
import { useNodeDialogState } from "./useNodeDialogState";

// open the advanced section when any advanced option is set away from its default
const hasAdvancedOptions = (data: HtmlToImageNodeData): boolean =>
  Boolean(data.waitFor);

export const HtmlToImageDialog: React.FC<
  BaseNodeDialogProps<HtmlToImageNodeData, HtmlToImageNodeData>
> = (props) => {
  const { isOpen, onClose, data } = props;

  const { values, setField, merged, handleSave } = useNodeDialogState(
    props,
    () => ({
      name: data.name || "",
      html: data.html || "",
      captureMode: data.captureMode || "fullPage",
      viewportWidth: data.viewportWidth ?? 1280,
      viewportHeight: data.viewportHeight ?? 720,
      waitFor: data.waitFor ?? 0,
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
          placeholder="HTML to Image"
          className="break-all w-full"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="html">HTML</Label>
        <RichTextarea
          id="html"
          value={values.html}
          onChange={(e) => setField("html", e.target.value)}
          placeholder="<html>...</html>"
          className="w-full min-h-[160px] font-mono"
        />
        <div className="text-xs text-muted-foreground break-words">
          The HTML to render. Use {"{{field}}"} to define dynamic parameters. An
          upstream input overrides this value.
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="captureMode">Capture Mode</Label>
        <Select
          value={values.captureMode}
          onValueChange={(value) =>
            setField("captureMode", value as HtmlToImageCaptureMode)
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
        <div className="text-xs text-muted-foreground break-words">
          Full Page captures the entire rendered content; Viewport captures only
          the configured viewport area.
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="viewportWidth">Viewport Width (px)</Label>
        <RichInput
          id="viewportWidth"
          type="number"
          value={String(values.viewportWidth)}
          onChange={(e) =>
            setField("viewportWidth", Math.max(1, parseInt(e.target.value) || 0))
          }
          placeholder="1280"
          className="w-full"
        />
      </div>

      {values.captureMode === "viewport" && (
        <div className="space-y-2">
          <Label htmlFor="viewportHeight">Viewport Height (px)</Label>
          <RichInput
            id="viewportHeight"
            type="number"
            value={String(values.viewportHeight)}
            onChange={(e) =>
              setField(
                "viewportHeight",
                Math.max(1, parseInt(e.target.value) || 0)
              )
            }
            placeholder="720"
            className="w-full"
          />
        </div>
      )}

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
