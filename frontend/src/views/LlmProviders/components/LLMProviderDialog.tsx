import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Textarea } from "@/components/textarea";
import { Switch } from "@/components/switch";
import { Button } from "@/components/button";
import { Loader2 } from "lucide-react";
import { toast } from "react-hot-toast";
import {
  createLLMProvider,
  getLLMProvidersFormSchemas,
  updateLLMProvider,
} from "@/services/llmProviders";
import { LLMProvider } from "@/interfaces/llmProvider.interface";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/select";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FieldSchema } from "@/interfaces/dynamicFormSchemas.interface";

interface LLMProviderDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onProviderSaved: (provider?: LLMProvider) => void;
  onProviderUpdated?: (provider: LLMProvider) => void;
  providerToEdit?: LLMProvider | null;
  mode?: "create" | "edit";
}

export function LLMProviderDialog({
  isOpen,
  onOpenChange,
  onProviderSaved,
  onProviderUpdated,
  providerToEdit = null,
  mode = "create",
}: LLMProviderDialogProps) {
  const [providerId, setProviderId] = useState<string>(providerToEdit?.id);
  const [name, setName] = useState(providerToEdit?.name ?? "");
  const [llmType, setLlmType] = useState<string>(
    providerToEdit?.llm_model_provider ?? ""
  );
  const [llmModel, setLlmModel] = useState<string>(
    providerToEdit?.llm_model ?? ""
  );

  const [isActive, setIsActive] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [connectionData, setConnectionData] = useState<
    Record<string, string | number | string[]>
  >(providerToEdit?.connection_data ?? {});

  const [showAdvanced, setShowAdvanced] = useState(false);
  const queryClient = useQueryClient();

  const { data, isLoading: isLoadingConfig } = useQuery({
    queryKey: ["supportedModels"],
    queryFn: () => getLLMProvidersFormSchemas(),
    refetchInterval: 5000,
    refetchOnWindowFocus: false,
    staleTime: 3000,
  });

  const supportedModels = data ?? {};

  useEffect(() => {
    if (isOpen) {
      if (providerToEdit) {
        setProviderId(providerToEdit.id);
        setName(providerToEdit.name);
        setLlmType(providerToEdit.llm_model_provider);
        setLlmModel(providerToEdit.llm_model);
        setConnectionData(providerToEdit.connection_data);
        setIsActive(providerToEdit.is_active === 1);
        setShowAdvanced(false);
      } else {
        resetForm();
      }
    }
  }, [isOpen, providerToEdit]);

  useEffect(() => {
    if (llmType && supportedModels[llmType]) {
      const defaultValues = supportedModels[llmType].fields.reduce(
        (acc, field) => {
          if (field.default !== undefined && !connectionData[field.name]) {
            acc[field.name] = field.default;
          }
          return acc;
        },
        {} as Record<string, string | number | string[]>
      );

      if (Object.keys(defaultValues).length > 0) {
        if (defaultValues.model) {
          setLlmModel(defaultValues.model.toString());
        }
        setConnectionData((prev) => ({
          ...prev,
          ...defaultValues,
        }));
      }
    }
  }, [llmType, supportedModels]);

  const resetForm = () => {
    setProviderId(undefined);
    setName("");
    setLlmType("");
    setConnectionData({});
    setIsActive(true);
    setShowAdvanced(false);
  };

  const handleConnectionDataChange = (
    field: FieldSchema,
    value: string | number | string[]
  ) => {
    if (field.name === "model") {
      setLlmModel(value as string);
    }
    setConnectionData((prev) => ({
      ...prev,
      [field.name]: value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const requiredFields = [
      { label: "Name", isEmpty: !name },
      { label: "Type", isEmpty: !llmType },
    ];

    const missingBasicFields = requiredFields
      .filter((field) => field.isEmpty)
      .map((field) => field.label);

    if (missingBasicFields.length > 0) {
      if (missingBasicFields.length === 1) {
        toast.error(`${missingBasicFields[0]} is required.`);
      } else {
        toast.error(`Please provide: ${missingBasicFields.join(", ")}.`);
      }
      return;
    }

    const providerConfig = supportedModels[llmType];
    if (!providerConfig) {
      toast.error("Invalid provider type.");
      return;
    }

    // Validate provider-specific required fields
    const missingFields = providerConfig.fields
      .filter((field) => field.required && !connectionData[field.name])
      .map((field) => field.label);

    if (missingFields.length > 0) {
      if (missingFields.length === 1) {
        toast.error(`${missingFields[0]} is required.`);
      } else {
        toast.error(`Please provide: ${missingFields.join(", ")}.`);
      }
      return;
    }

    setIsSubmitting(true);
    try {
      const data = {
        name,
        llm_model_provider: llmType,
        llm_model: llmModel,
        connection_data: connectionData,
        is_active: isActive ? 1 : 0,
      };

      if (mode === "create") {
        const created = await createLLMProvider(data);
        toast.success("LLM provider created successfully.");
        queryClient.invalidateQueries({ queryKey: ["llmProviders"] });
        onProviderSaved(created);
      } else {
        if (!providerId) throw new Error("Missing provider ID");
        const updated = await updateLLMProvider(providerId, data);
        toast.success("LLM provider updated successfully.");
        queryClient.invalidateQueries({ queryKey: ["llmProviders"] });
        if (onProviderUpdated) {
          onProviderUpdated(updated);
        }
      }

      onOpenChange(false);
      resetForm();
    } catch (error) {
      toast.error(
        `Failed to ${mode === "create" ? "create" : "update"} LLM provider.`
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderField = (field: FieldSchema) => {
    const value = connectionData[field.name] ?? field.default ?? "";

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
  const requiredFields =
    supportedModels[llmType]?.fields.filter((field) => field.required) ?? [];
  const optionalFields =
    supportedModels[llmType]?.fields.filter((field) => !field.required) ?? [];
  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px] p-0 overflow-hidden">
        <form
          onSubmit={handleSubmit}
          className="max-h-[90vh] overflow-y-auto overflow-x-hidden flex flex-col"
        >
          <DialogHeader className="p-6 pb-4">
            <DialogTitle>
              {mode === "create" ? "Create LLM Provider" : "Edit LLM Provider"}
            </DialogTitle>
          </DialogHeader>
          <div className="px-6 pb-6 space-y-4">
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
                    {Object.entries(supportedModels).map(
                      ([type, providerConfig]) => (
                        <SelectItem key={type} value={type}>
                          {providerConfig.name}
                        </SelectItem>
                      )
                    )}
                  </SelectContent>
                </Select>
              )}
            </div>

            {llmType && supportedModels[llmType] && (
              <>
                <div className="space-y-4">
                  {requiredFields.map((field) => (
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
                  {showAdvanced &&
                    optionalFields.map((field) => (
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
          </div>

          <DialogFooter className="px-6 py-4 border-t">
            <div className="flex justify-end gap-3 w-full">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : null}
                {mode === "create" ? "Create" : "Update"}
              </Button>
            </div>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
