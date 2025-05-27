import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/dialog";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Textarea } from "@/components/textarea";
import { Switch } from "@/components/switch";
import { Button } from "@/components/button";
import { Loader2 } from "lucide-react";
import { toast } from "react-hot-toast";
import { createLLMProvider, updateLLMProvider } from "@/services/llmProviders";
import {
  LLMProvider,
  LLMProviderField,
} from "@/interfaces/llmProvider.interface";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/select";
import { getSupportedModels } from "@/services/api";
import { useQuery } from "@tanstack/react-query";

interface LLMProviderDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onProviderSaved: () => void;
  providerToEdit?: LLMProvider | null;
  mode?: "create" | "edit";
}

export function LLMProviderDialog({
  isOpen,
  onOpenChange,
  onProviderSaved,
  providerToEdit = null,
  mode = "create",
}: LLMProviderDialogProps) {
  const [name, setName] = useState("");
  const [llmType, setLlmType] = useState("");
  const [llmModel, setLlmModel] = useState("");
  const [connectionData, setConnectionData] = useState<
    Record<string, string | number | string[]>
  >({});
  const [isActive, setIsActive] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [providerId, setProviderId] = useState<string>();
  const [showAdvanced, setShowAdvanced] = useState(false);

  const {
    data,
    isLoading:isLoadingConfig,
  } = useQuery({
    queryKey: ["supportedModels"],
    queryFn: () => getSupportedModels(),
    refetchInterval: 5000,
    refetchOnWindowFocus: false,
    staleTime: 3000,
  });

  const supportedModels = data??{};

  useEffect(() => {
    if (isOpen) {
      resetForm();
      if (providerToEdit && mode === "edit") {
        setProviderId(providerToEdit.id);
        setName(providerToEdit.name);
        setLlmType(providerToEdit.llm_model_provider);
        setLlmModel(providerToEdit.llm_model);
        setConnectionData(providerToEdit.connection_data);
        setIsActive(providerToEdit.is_active === 1);
      }
    }
  }, [isOpen, providerToEdit, mode]);


  const resetForm = () => {
    setProviderId(undefined);
    setName("");
    setLlmType("");
    setConnectionData({});
    setIsActive(true);
    setShowAdvanced(false);
  };

  const handleConnectionDataChange = (
    field: LLMProviderField,
    value: string | number | string[]
  ) => {
    setConnectionData((prev) => ({
      ...prev,
      [field.name]: value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!name || !llmType) {
      toast.error("Name and type are required");
      return;
    }

    const providerConfig = supportedModels[llmType];
    if (!providerConfig) {
      toast.error("Invalid provider type");
      return;
    }

    // Validate required fields
    const missingFields = providerConfig.fields
      .filter((field) => field.required && !connectionData[field.name])
      .map((field) => field.label);

    if (missingFields.length > 0) {
      toast.error(`Missing required fields: ${missingFields.join(", ")}`);
      return;
    }

    setIsSubmitting(true);
    try {
      const data = {
        name,
        llm_model_provider: llmType,
        llm_model: String(connectionData.model || ""),
        connection_data: connectionData,
        is_active: isActive ? 1 : 0,
      };

      if (mode === "create") {
        await createLLMProvider(data);
        toast.success("LLM Provider created");
      } else {
        if (!providerId) throw new Error("Missing provider ID");
        await updateLLMProvider(providerId, data);
        toast.success("LLM Provider updated");
      }

      onProviderSaved();
      onOpenChange(false);
      resetForm();
    } catch (error) {
      toast.error(
        `Failed to ${mode === "create" ? "create" : "update"} provider`
      );
      console.error(error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderField = (field: LLMProviderField) => {
    const value = connectionData[field.name] ?? field.default;

    switch (field.type) {
      case "select":
        return (
          <Select
            value={value as string}
            onValueChange={(val) => handleConnectionDataChange(field, val)}
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder={`Select ${field.label}`} />
            </SelectTrigger>
            <SelectContent>
              {field.options?.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        );
      case "number":
        return (
          <Input
            type="number"
            value={value as number}
            onChange={(e) =>
              handleConnectionDataChange(field, parseFloat(e.target.value))
            }
            min={field.min}
            max={field.max}
            step={field.step}
            placeholder={field.label}
          />
        );
      case "password":
        return (
          <Input
            type="password"
            value={value as string}
            onChange={(e) => handleConnectionDataChange(field, e.target.value)}
            placeholder={field.label}
          />
        );
      case "tags":
        return (
          <Textarea
            value={Array.isArray(value) ? value.join(", ") : ""}
            onChange={(e) =>
              handleConnectionDataChange(
                field,
                e.target.value.split(",").map((tag) => tag.trim())
              )
            }
            placeholder={field.label}
            rows={2}
          />
        );
      default:
        return (
          <Input
            type="text"
            value={value as string}
            onChange={(e) => handleConnectionDataChange(field, e.target.value)}
            placeholder={field.label}
          />
        );
    }
  };
  const requiredFields = supportedModels[llmType]?.fields.filter((field) => field.required) ?? [];
  const optionalFields = supportedModels[llmType]?.fields.filter((field) => !field.required) ?? [];
  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {mode === "create" ? "Create LLM Provider" : "Edit LLM Provider"}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Provider name"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="llm_type">Type</Label>
            {isLoadingConfig ? (
              <div className="flex items-center justify-center p-4">
                <Loader2 className="w-6 h-6 animate-spin" />
              </div>
            ) : (
              <Select
                value={llmType}
                onValueChange={(value) => {
                  setLlmType(value);
                  setConnectionData({});
                }}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select LLM Type" />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(supportedModels).map(([type, providerConfig]) => (
                    <SelectItem key={type} value={type}>
                      {providerConfig.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>

          {llmType && supportedModels[llmType] && (
            <>
              <div className="space-y-4">
                {requiredFields
                  .map((field) => (
                    <div key={field.name} className="space-y-2">
                      <Label htmlFor={field.name}>
                        {field.label}
                        {field.required && (
                          <span className="text-red-500 ml-1">*</span>
                        )}
                      </Label>
                      {renderField(field)}
                      {field.description && (
                        <p className="text-sm text-muted-foreground">
                          {field.description}
                        </p>
                      )}
                    </div>
                  ))}
              </div>
              <div className="flex items-center gap-2 border-t pt-4">
                <div className="flex items-center gap-2">
                  <Label htmlFor="is_active">Active</Label>
                  <Switch
                    id="is_active"
                    checked={isActive}
                    onCheckedChange={setIsActive}
                  />
                </div>
                <div className="flex-1" />
                {optionalFields.length > 0 && (
                  <div className="flex items-center gap-2">
                    <Label htmlFor="show_advanced">Advanced</Label>
                    <Switch
                      id="show_advanced"
                    checked={showAdvanced}
                    onCheckedChange={setShowAdvanced}
                  />
                </div>
                )}
              </div>

              <div className="space-y-4">
                {showAdvanced && optionalFields
                  .map((field) => (
                    <div key={field.name} className="space-y-2">
                      <Label htmlFor={field.name}>
                        {field.label}
                        {field.required && (
                          <span className="text-red-500 ml-1">*</span>
                        )}
                      </Label>
                      {renderField(field)}
                      {field.description && (
                        <p className="text-sm text-muted-foreground">
                          {field.description}
                        </p>
                      )}
                    </div>
                  ))}
              </div>
            </>
          )}

          <DialogFooter>
            <Button type="submit" disabled={isSubmitting} className="w-full">
              {isSubmitting ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : null}
              {mode === "create" ? "Create" : "Update"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
