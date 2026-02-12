import React, { useState, useEffect } from "react";
import { Button } from "@/components/button";
import { Label } from "@/components/label";
import { Save, HelpCircle } from "lucide-react";
import { Input } from "@/components/input";

import { DataMapperNodeData } from "@/views/AIAgents/Workflows/types/nodes";
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/hover-card";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-twilight";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { DraggableAceEditor } from "../components/custom/DraggableAceEditor";

type DataMapperDialogProps = BaseNodeDialogProps<
  DataMapperNodeData,
  DataMapperNodeData
>;

export const DataMapperDialog: React.FC<DataMapperDialogProps> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const [name, setName] = useState(data.name);
  const [pythonScript, setPythonScript] = useState(data.pythonScript);

  useEffect(() => {
    if (isOpen) {
      setName(data.name);
      setPythonScript(data.pythonScript);
    }
  }, [isOpen, data]);

  const handleSave = () => {
    const updatedData = {
      ...data,
      name,
      pythonScript,
    };
    onUpdate(updatedData);
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
        pythonScript,
      }}
    >
      <div className="space-y-4">
        <div>
          <Label>Node Name</Label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Enter the name of this node"
            className="w-full"
          />
        </div>
      </div>

      <div className="space-y-4">
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Label>Python Script</Label>
              <HoverCard>
                <HoverCardTrigger>
                  <HelpCircle className="h-4 w-4 text-gray-500" />
                </HoverCardTrigger>
                <HoverCardContent className="w-80">
                  <div className="space-y-2">
                    <p className="text-sm font-medium">
                      Python Script Guidelines:
                    </p>
                    <ul className="text-xs space-y-1">
                      <li>
                        • Input data is available as <code>input_data</code>
                      </li>
                      <li>
                        • Use <code>return</code> to output the result
                      </li>
                      <li>• Output must match the selected output type</li>
                      <li>• Access nested properties with dot notation</li>
                      <li>• Use Python standard library functions</li>
                      <li>• Scripts execute on real Python backend</li>
                    </ul>
                  </div>
                </HoverCardContent>
              </HoverCard>
            </div>
          </div>
          <DraggableAceEditor
            id="python-editor"
            name="python-editor"
            mode="python"
            theme="twilight"
            value={pythonScript}
            onChange={setPythonScript}
            width="100%"
            height="100%"
            placeholder="Enter your Python transformation script here..."
          />
        </div>
      </div>
    </NodeConfigPanel>
  );
};
