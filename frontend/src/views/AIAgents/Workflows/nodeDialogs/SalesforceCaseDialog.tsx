import React, { useState, useEffect } from "react";
import { toast } from "react-hot-toast";
import { SalesforceCaseNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { RichInput } from "@/components/richInput";
import { Label } from "@/components/label";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { Save, Plus, X } from "lucide-react";
import { BaseNodeDialogProps } from "./base";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { getAllAppSettings } from "@/services/appSettings";
import { AppSetting } from "@/interfaces/app-setting.interface";
import { AppSettingDialog } from "@/views/AppSettings/components/AppSettingDialog";
import { CreateNewSelectItem } from "@/components/CreateNewSelectItem";
import { DraggableInput } from "../components/custom/DraggableInput";
import { DraggableTextArea } from "../components/custom/DraggableTextArea";
import { useNodeDialogState } from "./useNodeDialogState";

type SalesforceCaseDialogProps = BaseNodeDialogProps<
  SalesforceCaseNodeData,
  SalesforceCaseNodeData
>;

export const SalesforceCaseDialog: React.FC<SalesforceCaseDialogProps> = (
  props
) => {
  const { isOpen, onClose, data } = props;

  const { values, setField, setValues, merged, handleSave } =
    useNodeDialogState(
      props,
      () => ({
        name: data.name || "",
        subject: data.subject || "",
        description: data.description || "",
        labelsCsv: (data.labels || []).join(", "),
        custom_fields: (data.custom_fields || []) as Array<{
          key: string;
          value: string;
        }>,
        app_settings_id: data.app_settings_id || "",
      }),
      (v) => {
        const labelsArr = v.labelsCsv
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean);
        return {
          name: v.name,
          subject: v.subject,
          description: v.description,
          labels: labelsArr.length > 0 ? labelsArr : undefined,
          custom_fields:
            v.custom_fields.length > 0 ? v.custom_fields : undefined,
          app_settings_id: v.app_settings_id || undefined,
        };
      }
    );

  const [appSettings, setAppSettings] = useState<AppSetting[]>([]);
  const [isLoadingAppSettings, setIsLoadingAppSettings] = useState(false);
  const [appSettingsError, setAppSettingsError] = useState(false);
  const [isCreateSettingOpen, setIsCreateSettingOpen] = useState(false);

  const fetchAppSettings = async () => {
    setIsLoadingAppSettings(true);
    setAppSettingsError(false);
    try {
      const settings = await getAllAppSettings();
      setAppSettings(settings);
    } catch (error) {
      setAppSettingsError(true);
    } finally {
      setIsLoadingAppSettings(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchAppSettings();
    }
  }, [isOpen, data]);

  const salesforceAppSettings = appSettings.filter((setting) => {
    const settingTypeLower = setting.type.toLowerCase();
    return settingTypeLower === "salesforce" && setting.is_active === 1;
  });

  const handleSaveClick = () => {
    // The backend node schema marks these required — block save with a clear
    // message instead of persisting a node that only fails at run time.
    const missing: string[] = [];
    if (!values.app_settings_id) missing.push("Configuration Vars");
    if (!values.subject.trim()) missing.push("Subject");
    if (!values.description.trim()) missing.push("Description");
    if (missing.length > 0) {
      toast.error(`Please provide: ${missing.join(", ")}.`);
      return;
    }

    handleSave();
  };

  const addCustomField = () => {
    setValues((v) => ({
      ...v,
      custom_fields: [...v.custom_fields, { key: "", value: "" }],
    }));
  };

  const removeCustomField = (index: number) => {
    setValues((v) => ({
      ...v,
      custom_fields: v.custom_fields.filter((_, i) => i !== index),
    }));
  };

  const updateCustomField = (
    index: number,
    field: "key" | "value",
    value: string
  ) => {
    setValues((v) => {
      const updated = [...v.custom_fields];
      updated[index] = { ...updated[index], [field]: value };
      return { ...v, custom_fields: updated };
    });
  };

  return (
    <>
      <NodeConfigPanel
        footer={
          <>
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button onClick={handleSaveClick}>
              <Save className="h-4 w-4 mr-2" />
              Save Changes
            </Button>
          </>
        }
        {...props}
        data={merged}
      >
        <div className="space-y-2">
          <Label htmlFor="node-name">Node Name</Label>
          <RichInput
            id="node-name"
            value={values.name}
            onChange={(e) => setField("name", e.target.value)}
            placeholder="Enter the name of this node"
            className="w-full"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="app-settings-id">Configuration Vars</Label>
          {appSettingsError ? (
            <div className="flex items-center justify-between gap-2 rounded-md border border-destructive/50 p-2">
              <p className="text-sm text-destructive">
                Failed to load configurations.
              </p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={fetchAppSettings}
              >
                Retry
              </Button>
            </div>
          ) : (
            <Select
              value={values.app_settings_id || ""}
              onValueChange={(value) => {
                if (value === "__create__") {
                  setIsCreateSettingOpen(true);
                  return;
                }
                setField("app_settings_id", value || "");
              }}
              disabled={isLoadingAppSettings}
            >
              <SelectTrigger className="w-full">
                <SelectValue
                  placeholder={
                    isLoadingAppSettings
                      ? "Loading configurations..."
                      : "Select configuration"
                  }
                />
              </SelectTrigger>
              <SelectContent>
                {salesforceAppSettings.length === 0 &&
                  !isLoadingAppSettings && (
                    <div className="px-2 py-1.5 text-sm text-muted-foreground">
                      No Salesforce configurations found.
                    </div>
                  )}
                {salesforceAppSettings.map((setting) => (
                  <SelectItem key={setting.id} value={setting.id}>
                    {setting.name}
                  </SelectItem>
                ))}
                <CreateNewSelectItem />
              </SelectContent>
            </Select>
          )}
        </div>

        <div className="space-y-2">
          <Label className="font-bold">Case Information</Label>
          <div className="space-y-2">
            <div className="space-y-2">
              <Label htmlFor="subject">Subject</Label>
              <DraggableInput
                id="subject"
                value={values.subject}
                onChange={(e) => setField("subject", e.target.value)}
                placeholder="Enter case subject"
                className="w-full"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <DraggableTextArea
                id="description"
                rows={4}
                value={values.description}
                onChange={(e) => setField("description", e.target.value)}
                placeholder="Enter the issue or request description"
                className="w-full resize-none"
              />
            </div>
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="labels" className="font-bold">
            Labels
          </Label>
          <DraggableInput
            id="labels"
            value={values.labelsCsv}
            onChange={(e) => setField("labelsCsv", e.target.value)}
            placeholder="e.g., billing, urgent, follow-up"
            className="w-full"
          />
          <p className="text-xs text-muted-foreground">
            Comma-separated. Each label is assigned to the created Case as a SalesForce
            Topic (requires “Topics for Objects” enabled on Case).
          </p>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label className="font-bold">Custom Fields</Label>
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
          <div className="space-y-2">
            {values.custom_fields.map((field, index) => (
              <div key={index} className="flex gap-2 items-end">
                <div className="flex-1 space-y-2">
                  <Label htmlFor={`custom-field-key-${index}`}>
                    Field API Name
                  </Label>
                  <DraggableInput
                    id={`custom-field-key-${index}`}
                    value={field.key}
                    onChange={(e) =>
                      updateCustomField(index, "key", e.target.value)
                    }
                    placeholder="e.g., Priority"
                    className="w-full"
                  />
                </div>
                <div className="flex-1 space-y-2">
                  <Label htmlFor={`custom-field-value-${index}`}>Value</Label>
                  <DraggableInput
                    id={`custom-field-value-${index}`}
                    value={field.value}
                    onChange={(e) =>
                      updateCustomField(index, "value", e.target.value)
                    }
                    placeholder="Enter field value"
                    className="w-full"
                  />
                </div>
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  className="h-10 w-10 flex-shrink-0 text-destructive hover:bg-destructive/10"
                  onClick={() => removeCustomField(index)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ))}
            {values.custom_fields.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No custom fields added. Click "Add Field" to add one.
              </p>
            )}
          </div>
        </div>
      </NodeConfigPanel>

      <AppSettingDialog
        isOpen={isCreateSettingOpen}
        onOpenChange={setIsCreateSettingOpen}
        mode="create"
        initialType="Salesforce"
        disableTypeSelect
        onSettingSaved={async (created) => {
          try {
            const settings = await getAllAppSettings();
            setAppSettings(settings);
          } catch (e) {
            // ignore
          }
          if (created?.id) setField("app_settings_id", created.id);
        }}
      />
    </>
  );
};
