import React, { useState, useEffect } from "react";
import { WhatsappNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { RichInput } from "@/components/richInput";
import { Label } from "@/components/label";
import { Save } from "lucide-react";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
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

type WhatsAppDialogProps = BaseNodeDialogProps<
  WhatsappNodeData,
  WhatsappNodeData
>;

export const WhatsAppDialog: React.FC<WhatsAppDialogProps> = (props) => {
  const { isOpen, onClose, data } = props;

  const { values, setField, merged, handleSave } = useNodeDialogState(
    props,
    () => ({
      name: data.name,
      message: data.message || "",
      recipient_number: data.recipient_number || "",
      app_settings_id: data.app_settings_id || "",
    }),
    (v) => ({
      name: v.name,
      message: v.message,
      recipient_number: v.recipient_number,
      app_settings_id: v.app_settings_id || undefined,
    })
  );

  const [appSettings, setAppSettings] = useState<AppSetting[]>([]);
  const [isLoadingAppSettings, setIsLoadingAppSettings] = useState(false);
  const [isCreateSettingOpen, setIsCreateSettingOpen] = useState(false);

  useEffect(() => {
    if (isOpen) {
      // Fetch app settings
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
          <Label htmlFor="name">Tool Name</Label>
          <RichInput
            id="name"
            value={values.name}
            onChange={(e) => setField("name", e.target.value)}
            placeholder="e.g., WhatsApp Message"
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
                    settingTypeLower === "whatsapp" && setting.is_active === 1
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
          <Label htmlFor="toNumber">Recipient Number</Label>
          <DraggableInput
            id="toNumber"
            value={values.recipient_number}
            onChange={(e) => setField("recipient_number", e.target.value)}
            placeholder="e.g., 15551234567"
            className="w-full"
          />
          <p className="text-xs text-muted-foreground">
            Include the country code in the phone number. You may use “+”, but
            not “00”.
          </p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="textMsg">Message</Label>
          <DraggableTextArea
            id="textMsg"
            size="body"
            value={values.message}
            onChange={(e) => setField("message", e.target.value)}
            placeholder="e.g., Please call me!"
            className="w-full"
          />
        </div>
      </NodeConfigPanel>
      <AppSettingDialog
        isOpen={isCreateSettingOpen}
        onOpenChange={setIsCreateSettingOpen}
        mode="create"
        initialType="WhatsApp"
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
