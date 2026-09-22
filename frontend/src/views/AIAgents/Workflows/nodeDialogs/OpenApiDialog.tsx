import React, { useEffect, useState } from "react";
import { OpenApiNodeData } from "../types/nodes";
import { BaseNodeDialogProps } from "./base";
import { useToast } from "@/hooks/useToast";
import { getAllLLMProviders } from "@/services/llmProviders";
import { LLMProvider } from "@/interfaces/llmProvider.interface";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { Button } from "@/components/button";
import { Save } from "lucide-react";
import { Label } from "@/components/label";
import { RichInput } from "@/components/richInput";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { CreateNewSelectItem } from "@/components/CreateNewSelectItem";
import { LLMProviderDialog } from "@/views/LlmProviders/components/LLMProviderDialog";
import { DraggableTextArea } from "../components/custom/DraggableTextArea";
import { FileUploader } from "@/components/FileUploader";
import { useNodeDialogState } from "./useNodeDialogState";

type OpenApiDialogProps = BaseNodeDialogProps<OpenApiNodeData, OpenApiNodeData>;

export const OpenApiDialog: React.FC<OpenApiDialogProps> = (props) => {
  const { isOpen, onClose, data } = props;

  const { values, setField, setValues, merged, handleSave } =
    useNodeDialogState(props, () => ({
      name: data.name || "",
      providerId: data.providerId || "",
      query: data.query || "",
      originalFileName: data.originalFileName || "",
      serverFilePath: (data.serverFilePath || "") as string | undefined,
      serverFileUrl: (data.serverFileUrl || "") as string | undefined,
    }));

  const [availableProviders, setAvailableProviders] = useState<LLMProvider[]>(
    [],
  );
  const { toast } = useToast();
  const [isCreateProviderOpen, setIsCreateProviderOpen] = useState(false);

  useEffect(() => {
    if (isOpen) {
      loadProviders();
    }
  }, [isOpen, data, toast]);

  const loadProviders = async () => {
    try {
      const providers = await getAllLLMProviders();
      setAvailableProviders(providers.filter((p) => p.is_active === 1));
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to load LLM providers",
        variant: "destructive",
      });
    }
  };

  return (
    <>
      <NodeConfigPanel
        isOpen={isOpen}
        onClose={onClose}
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
        <div className="space-y-4">
          {/* Node Name */}
          <div className="space-y-2">
            <Label htmlFor="name">Node Name</Label>
            <RichInput
              id="name"
              value={values.name}
              onChange={(e) => setField("name", e.target.value)}
              placeholder="Enter the name of this node"
              className="w-full"
            />
          </div>

          {/* LLM Provider */}
          <div className="space-y-2">
            <Label htmlFor="provider">LLM Provider</Label>
            <Select
              value={values.providerId || ""}
              onValueChange={(value) => {
                if (value === "__create__") {
                  setIsCreateProviderOpen(true);
                  return;
                }
                setField("providerId", value);
              }}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select an LLM provider" />
              </SelectTrigger>
              <SelectContent>
                {availableProviders.map((provider) => (
                  <SelectItem key={provider.id} value={provider.id!}>
                    {provider.name}
                  </SelectItem>
                ))}
                <CreateNewSelectItem />
              </SelectContent>
            </Select>
          </div>

          {/* Specification File */}
          <FileUploader
            label="Specification File"
            acceptedFileTypes={[".json", ".yaml", ".yml"]}
            initialServerFilePath={values.serverFilePath}
            initialServerFileUrl={values.serverFileUrl}
            initialOriginalFileName={values.originalFileName}
            onUploadComplete={(result) => {
              setValues((v) => ({
                ...v,
                originalFileName: result.original_filename,
                serverFilePath: result.file_path,
                serverFileUrl: result.file_url,
              }));
            }}
            onRemove={() => {
              setValues((v) => ({
                ...v,
                originalFileName: "",
                serverFilePath: undefined,
                serverFileUrl: undefined,
              }));
            }}
            placeholder="Select a JSON or YAML file to upload"
          />

          {/* Query */}
          <div className="space-y-2">
            <Label htmlFor="query">Query</Label>
            <DraggableTextArea
              id="query"
              value={values.query}
              onChange={(e) => setField("query", e.target.value)}
              placeholder="Ask a question about the specification file..."
              className="w-full h-24 text-sm resize-none"
            />
          </div>
        </div>
      </NodeConfigPanel>

      <LLMProviderDialog
        isOpen={isCreateProviderOpen}
        onOpenChange={setIsCreateProviderOpen}
        onProviderSaved={async (provider) => {
          await loadProviders();
          if (provider?.id) {
            setField("providerId", provider.id);
          }
        }}
        mode="create"
      />
    </>
  );
};
