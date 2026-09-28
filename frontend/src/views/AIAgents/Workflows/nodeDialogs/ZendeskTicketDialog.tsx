import React, { useState, useEffect } from "react";
import { ZendeskTicketNodeData } from "../types/nodes";
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

type ZendeskTicketDialogProps = BaseNodeDialogProps<
  ZendeskTicketNodeData,
  ZendeskTicketNodeData
>;

export const ZendeskTicketDialog: React.FC<ZendeskTicketDialogProps> = (
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
        requester_name: data.requester_name || "",
        requester_email: data.requester_email || "",
        tagsCsv: (data.tags || []).join(", "),
        custom_fields: (data.custom_fields || []) as Array<{
          id: string;
          value: string | number;
        }>,
        app_settings_id: data.app_settings_id || "",
      }),
      (v) => {
        const tagsArr = v.tagsCsv
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean);
        return {
          name: v.name,
          subject: v.subject,
          description: v.description,
          requester_name: v.requester_name,
          requester_email: v.requester_email,
          tags: tagsArr,
          custom_fields:
            v.custom_fields.length > 0 ? v.custom_fields : undefined,
          app_settings_id: v.app_settings_id || undefined,
        };
      }
    );

  const [appSettings, setAppSettings] = useState<AppSetting[]>([]);
  const [isLoadingAppSettings, setIsLoadingAppSettings] = useState(false);
  const [isCreateSettingOpen, setIsCreateSettingOpen] = useState(false);

  useEffect(() => {
    if (isOpen) {
      const fetchAppSettings = async () => {
        setIsLoadingAppSettings(true);
        try {
          const settings = await getAllAppSettings();
          setAppSettings(settings);
        } catch (error) {
          // ignore
        } finally {
          setIsLoadingAppSettings(false);
        }
      };

      fetchAppSettings();
    }
  }, [isOpen, data]);

  const addCustomField = () => {
    setValues((v) => ({
      ...v,
      custom_fields: [...v.custom_fields, { id: "", value: "" }],
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
    field: "id" | "value",
    value: string | number
  ) => {
    setValues((v) => {
      const updated = [...v.custom_fields];
      if (field === "id") {
        updated[index] = { ...updated[index], id: String(value) };
      } else {
        updated[index] = { ...updated[index], value };
      }
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
          <Label htmlFor="app-settings-id">Configuration Vars (Optional)</Label>
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
              <SelectValue placeholder="Select configuration (optional)" />
            </SelectTrigger>
            <SelectContent>
              {appSettings
                .filter((setting) => {
                  const settingTypeLower = setting.type.toLowerCase();
                  return (
                    settingTypeLower === "zendesk" && setting.is_active === 1
                  );
                })
                .map((setting) => (
                  <SelectItem key={setting.id} value={setting.id}>
                    {setting.name}
                  </SelectItem>
                ))}
              <CreateNewSelectItem />
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label className="font-bold">Ticket Information</Label>
          <div className="space-y-2">
            <div className="space-y-2">
              <Label htmlFor="subject">Subject</Label>
              <DraggableInput
                id="subject"
                value={values.subject}
                onChange={(e) => setField("subject", e.target.value)}
                placeholder="Enter ticket subject"
                className="w-full"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <DraggableTextArea
                id="description"
                size="body"
                value={values.description}
                onChange={(e) => setField("description", e.target.value)}
                placeholder="Enter the issue or request description"
                className="w-full"
              />
            </div>
          </div>
        </div>

        <div className="space-y-2">
          <Label className="font-bold">Requester Information</Label>
          <div className="space-y-2">
            <div className="space-y-2">
              <Label htmlFor="requester_name">Requester Name</Label>
              <DraggableInput
                id="requester_name"
                value={values.requester_name}
                onChange={(e) => setField("requester_name", e.target.value)}
                placeholder="e.g., Alice Smith"
                className="w-full"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="requester_email">Requester Email</Label>
              <DraggableInput
                id="requester_email"
                type="email"
                value={values.requester_email}
                onChange={(e) => setField("requester_email", e.target.value)}
                placeholder="e.g., alice@example.com"
                className="w-full break-all"
              />
            </div>
          </div>
        </div>

        <div className="space-y-2">
          <Label className="font-bold">Tags</Label>
          <div className="space-y-2">
            <div className="space-y-2">
              <Label htmlFor="tags">Tags</Label>
              <DraggableInput
                id="tags"
                value={values.tagsCsv}
                onChange={(e) => setField("tagsCsv", e.target.value)}
                placeholder="e.g., support, urgent, follow-up"
                className="w-full"
              />
            </div>
          </div>
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
                  <Label htmlFor={`custom-field-id-${index}`}>Field ID</Label>
                  <DraggableInput
                    id={`custom-field-id-${index}`}
                    value={field.id}
                    onChange={(e) =>
                      updateCustomField(index, "id", e.target.value)
                    }
                    placeholder="e.g., 123456"
                    className="w-full"
                  />
                </div>
                <div className="flex-1 space-y-2">
                  <Label htmlFor={`custom-field-value-${index}`}>Value</Label>
                  <DraggableInput
                    id={`custom-field-value-${index}`}
                    value={field.value.toString()}
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
        initialType="Zendesk"
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
