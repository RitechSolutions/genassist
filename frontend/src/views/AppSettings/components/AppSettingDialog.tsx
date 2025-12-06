import { useState, useEffect, useMemo } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import {
  createAppSetting,
  getAppSettingsFormSchemas,
  updateAppSetting,
} from "@/services/appSettings";
import { Switch } from "@/components/switch";
import { Label } from "@/components/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { toast } from "react-hot-toast";
import { Loader2, Plus, X } from "lucide-react";
import { AppSetting } from "@/interfaces/app-setting.interface";
import { useQuery } from "@tanstack/react-query";
import { FieldSchema } from "@/interfaces/dynamicFormSchemas.interface";

interface AppSettingDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onSettingSaved: (createdOrUpdated?: AppSetting) => void;
  settingToEdit?: AppSetting | null;
  mode?: "create" | "edit";
  initialType?: AppSetting["type"];
  // When true, the Type select is disabled
  disableTypeSelect?: boolean;
}

export function AppSettingDialog({
  isOpen,
  onOpenChange,
  onSettingSaved,
  settingToEdit = null,
  mode = "create",
  initialType,
  disableTypeSelect = false,
}: AppSettingDialogProps) {
  const [name, setName] = useState("");
  const [type, setType] = useState<AppSetting["type"]>("Other");
  const [values, setValues] = useState<Record<string, string>>({});
  const [description, setDescription] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [customFields, setCustomFields] = useState<
    Array<{ key: string; value: string }>
  >([{ key: "", value: "" }]);

  const { data, isLoading: isLoadingConfig } = useQuery({
    queryKey: ["appSettingSchemas"],
    queryFn: () => getAppSettingsFormSchemas(),
    refetchInterval: 5000,
    refetchOnWindowFocus: false,
    staleTime: 3000,
  });

  const appSettingSchemas = data ?? {};

  useEffect(() => {
    if (isOpen) {
      resetForm();
      if (settingToEdit && mode === "edit") {
        populateFormWithSetting(settingToEdit);
      } else if (mode === "create" && initialType) {
        setType(initialType);
      }
    }
  }, [isOpen, settingToEdit, mode]);

  const resetForm = () => {
    setName("");
    setType("Other");
    setValues({});
    setDescription("");
    setIsActive(true);
    setCustomFields([{ key: "", value: "" }]);
  };

  const populateFormWithSetting = (setting: AppSetting) => {
    setName(setting.name);
    setType(setting.type);
    setValues(setting.values || {});
    setDescription(setting.description || "");
    setIsActive(setting.is_active === 1);

    // For "Other" type, populate custom fields
    if (setting.type === "Other") {
      const fields = Object.entries(setting.values || {}).map(
        ([key, value]) => ({
          key,
          value,
        })
      );
      setCustomFields(fields.length > 0 ? fields : [{ key: "", value: "" }]);
    } else {
      // For non-Other types, ensure custom fields are reset
      setCustomFields([{ key: "", value: "" }]);
    }
  };

  const handleValuesChange = (field: FieldSchema, value: string) => {
    setValues((prev) => ({
      ...prev,
      [field.name]: value,
    }));
  };

  const handleCustomFieldChange = (
    index: number,
    field: "key" | "value",
    value: string
  ) => {
    setCustomFields((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };
      return updated;
    });
  };

  const addCustomField = () => {
    setCustomFields((prev) => [...prev, { key: "", value: "" }]);
  };

  const removeCustomField = (index: number) => {
    setCustomFields((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const missingFields: string[] = [];

    if (!name) missingFields.push("Name");
    if (!type) missingFields.push("Type");

    if (missingFields.length > 0) {
      if (missingFields.length === 1) {
        toast.error(`${missingFields[0]} is required.`);
      } else {
        toast.error(`Please provide: ${missingFields.join(", ")}.`);
      }
      return;
    }

    // Validate schema-based fields
    if (type !== "Other" && appSettingSchemas[type]) {
      const schema = appSettingSchemas[type];
      const schemaMissing = schema.fields
        .filter((field) => field.required && !values[field.name])
        .map((field) => field.label);

      if (schemaMissing.length > 0) {
        if (schemaMissing.length === 1) {
          toast.error(`${schemaMissing[0]} is required.`);
        } else {
          toast.error(`Please provide: ${schemaMissing.join(", ")}.`);
        }
        return;
      }
    }

    // For "Other" type, build values from custom fields
    let finalValues = values;
    if (type === "Other") {
      finalValues = {};
      customFields.forEach((field) => {
        if (field.key.trim()) {
          finalValues[field.key.trim()] = field.value || "";
        }
      });

      if (Object.keys(finalValues).length === 0) {
        toast.error("Please add at least one custom field.");
        return;
      }
    }

    setIsSubmitting(true);
    try {
      const data: Partial<AppSetting> = {
        name,
        type,
        values: finalValues,
        description: description || undefined,
        is_active: isActive ? 1 : 0,
      };

      if (mode === "create") {
        const created = await createAppSetting(data);
        toast.success("App setting created successfully.");
        onSettingSaved(created);
      } else {
        if (!settingToEdit?.id) throw new Error("Missing app setting ID");
        const updated = await updateAppSetting(settingToEdit.id, data);
        toast.success("App setting updated successfully.");
        onSettingSaved(updated);
      }

      onOpenChange(false);
      resetForm();
    } catch (error) {
      toast.error(`Failed to ${mode} app setting.`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderField = (field: FieldSchema) => {
    const value = values[field.name] ?? field.default;

    switch (field.type) {
      case "select":
        return (
          <Select
            value={value as string}
            onValueChange={(val) => handleValuesChange(field, val)}
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
            value={value as string}
            onChange={(e) => handleValuesChange(field, e.target.value)}
            placeholder={field.placeholder || field.label}
          />
        );
      case "password":
        return (
          <Input
            type="password"
            value={value as string}
            onChange={(e) => handleValuesChange(field, e.target.value)}
            placeholder={field.placeholder || field.label}
          />
        );
      default:
        return (
          <Input
            type="text"
            value={value as string}
            onChange={(e) => handleValuesChange(field, e.target.value)}
            placeholder={field.placeholder || field.label}
          />
        );
    }
  };

  const requiredFields =
    type !== "Other" && appSettingSchemas[type]
      ? appSettingSchemas[type].fields.filter((f) => f.required)
      : [];
  const optionalFields =
    type !== "Other" && appSettingSchemas[type]
      ? appSettingSchemas[type].fields.filter((f) => !f.required)
      : [];

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px] p-0 overflow-hidden">
        <form
          onSubmit={handleSubmit}
          className="max-h-[90vh] overflow-y-auto overflow-x-hidden flex flex-col"
        >
          <DialogHeader className="p-6 pb-4">
            <DialogTitle>
              {mode === "create" ? "Create Configuration" : "Edit Configuration"}
            </DialogTitle>
          </DialogHeader>

          <div className="px-6 pb-6 space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Name"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="type">Type</Label>
              {isLoadingConfig ? (
                <div className="flex items-center justify-center p-4">
                  <Loader2 className="w-6 h-6 animate-spin" />
                </div>
              ) : (
                <Select
                  value={type}
                  onValueChange={(value) => {
                    const newType = value as AppSetting["type"];
                    setType(newType);

                    if (newType === "Other") {
                      setValues({});
                      setCustomFields([{ key: "", value: "" }]);
                    } else {
                      if (type === "Other" || mode === "create") {
                        setValues({});
                      }
                      setCustomFields([{ key: "", value: "" }]);
                    }
                  }}
                >
                  <SelectTrigger className="w-full" disabled={disableTypeSelect}>
                    <SelectValue placeholder="Select Type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Zendesk">Zendesk</SelectItem>
                    <SelectItem value="WhatsApp">WhatsApp</SelectItem>
                    <SelectItem value="Gmail">Gmail</SelectItem>
                    <SelectItem value="Microsoft">Microsoft</SelectItem>
                    <SelectItem value="Slack">Slack</SelectItem>
                    <SelectItem value="Jira">Jira</SelectItem>
                    <SelectItem value="Other">Other</SelectItem>
                  </SelectContent>
                </Select>
              )}
            </div>

            {type && (
              <>
                {type === "Other" ? (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <Label>Custom Fields</Label>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={addCustomField}
                      >
                        <Plus className="w-4 h-4 mr-1" />
                        Add Field
                      </Button>
                    </div>
                    {customFields.map((field, index) => (
                      <div key={index} className="flex gap-2 items-end">
                        <div className="flex-1 space-y-2">
                          <Label htmlFor={`custom-key-${index}`}>Key</Label>
                          <Input
                            id={`custom-key-${index}`}
                            value={field.key}
                            onChange={(e) =>
                              handleCustomFieldChange(
                                index,
                                "key",
                                e.target.value
                              )
                            }
                            placeholder="Field key"
                          />
                        </div>
                        <div className="flex-1 space-y-2">
                          <Label htmlFor={`custom-value-${index}`}>Value</Label>
                          <Input
                            id={`custom-value-${index}`}
                            value={field.value}
                            onChange={(e) =>
                              handleCustomFieldChange(
                                index,
                                "value",
                                e.target.value
                              )
                            }
                            placeholder="Field value"
                            type="password"
                          />
                        </div>
                        {customFields.length > 1 && (
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => removeCustomField(index)}
                          >
                            <X className="w-4 h-4" />
                          </Button>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
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
                    {optionalFields.length > 0 && (
                      <div className="space-y-4 pt-2 border-t">
                        {optionalFields.map((field) => (
                          <div key={field.name} className="space-y-2">
                            <Label htmlFor={field.name}>{field.label}</Label>
                            {renderField(field)}
                            {field.description && (
                              <p className="text-sm text-muted-foreground">
                                {field.description}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </>
            )}

            <div className="space-y-2">
              <Label htmlFor="description">Description (Optional)</Label>
              <Input
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Description"
              />
            </div>

            <div className="flex items-center gap-2 pt-2 border-t">
              <Label htmlFor="is_active">Active</Label>
              <Switch
                id="is_active"
                checked={isActive}
                onCheckedChange={setIsActive}
              />
            </div>
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
                {isSubmitting && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                {mode === "create" ? "Create" : "Update"}
              </Button>
            </div>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
