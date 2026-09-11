import React, { useState } from "react";
import { Textarea } from "@/components/ui/textarea";
import { PythonCodeNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { Label } from "@/components/label";
import { Save, Sparkles } from "lucide-react";
import { toast } from "react-hot-toast";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-twilight";
import { generatePythonTemplate } from "@/services/workflows";
import { DraggableAceEditor } from "../components/custom/DraggableAceEditor";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { RichInput } from "@/components/richInput";
import { useNodeDialogState } from "./useNodeDialogState";

type PythonCodeDialogProps = BaseNodeDialogProps<
  PythonCodeNodeData,
  PythonCodeNodeData
>;

export const PythonCodeDialog: React.FC<PythonCodeDialogProps> = (props) => {
  const { onClose, data } = props;

  const { values, setField, merged, handleSave } = useNodeDialogState(
    props,
    () => ({
      name: data.name || "",
      code: data.code || "",
      unwrap: data.unwrap || false,
    })
  );

  const [loading, setLoading] = useState(false);
  const [isPromptDialogOpen, setIsPromptDialogOpen] = useState(false);
  const [templatePrompt, setTemplatePrompt] = useState("");

  const handleGenerateTemplate = async (prompt?: string) => {
    try {
      setLoading(true);
      const result = await generatePythonTemplate({}, prompt);
      if (result && typeof result === "object" && "template" in result) {
        setField("code", result.template as string);
        toast.success("Template generated successfully.");
      }
    } catch (err) {
      toast.error("Failed to generate template.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
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
        showUnwrap={true}
        onUnwrapChange={(val) => setField("unwrap", val)}
      >
        <div className="space-y-2">
          <Label htmlFor="name">Name</Label>
          <RichInput
            id="name"
            value={values.name}
            onChange={(e) => setField("name", e.target.value)}
            placeholder="API Tool"
            className="break-all w-full"
          />
        </div>
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <Label>Python Code</Label>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                className="h-6 text-xs"
                onClick={() => setIsPromptDialogOpen(true)}
                disabled={loading}
              >
                <Sparkles className="h-3 w-3 mr-1" />
                Generate Template
              </Button>
            </div>
          </div>
          <DraggableAceEditor
            id="python-editor"
            name="python-editor"
            mode="python"
            theme="twilight"
            value={values.code}
            onChange={(value: string) => setField("code", value)}
            width="100%"
            height="100%"
            setOptions={{
              showLineNumbers: true,
              tabSize: 4,
              useWorker: false,
              enableBasicAutocompletion: true,
              enableLiveAutocompletion: true,
              enableSnippets: true,
              showPrintMargin: false,
              fontSize: 14,
              wrap: true,
            }}
          />
          <div className="text-xs text-muted-foreground">
            <ul className="list-disc list-inside space-y-1">
              <li className="break-words">
                Use <code className="bg-muted px-1 rounded">params</code>{" "}
                dictionary to access input parameters
              </li>
              <li className="break-words">
                Store your return value in{" "}
                <code className="bg-muted px-1 rounded">result</code>{" "}
                variable
              </li>
              <li className="break-words">
                Available libraries: json, requests, datetime, math, re
              </li>
              <li className="break-words">
                Code runs in a sandboxed environment with limited resources
              </li>
              <li className="break-words">Maximum execution time: 5 seconds</li>
            </ul>
          </div>
        </div>
      </NodeConfigPanel>

      {/* Prompt Dialog for Template Generation */}
      <Dialog open={isPromptDialogOpen} onOpenChange={setIsPromptDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Include a prompt?</DialogTitle>
            <DialogDescription>
              Would you like to include a prompt for template generation?
              (Optional)
            </DialogDescription>
          </DialogHeader>
          <Textarea
            size="body"
            className="mt-2"
            placeholder="Enter a prompt (optional)"
            value={templatePrompt}
            onChange={(e) => setTemplatePrompt(e.target.value)}
          />
          <DialogFooter className="mt-4">
            <Button
              variant="outline"
              onClick={() => {
                setIsPromptDialogOpen(false);
                setTemplatePrompt("");
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={() => {
                setIsPromptDialogOpen(false);
                handleGenerateTemplate(templatePrompt);
                setTemplatePrompt("");
              }}
              disabled={loading}
            >
              <Sparkles className="h-4 w-4 mr-2" />
              Generate
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};
