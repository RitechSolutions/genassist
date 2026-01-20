import React, { useState, useEffect } from "react";
import { WhatsappNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
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

type WhatsAppDialogProps = BaseNodeDialogProps<
  WhatsappNodeData,
  WhatsappNodeData
>;

export const WhatsAppDialog: React.FC<WhatsAppDialogProps> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;
  const [name, setName] = useState(data.name);
  const [textMsg, setMessage] = useState(data.message || "");
  const [toNumber, setToNumber] = useState(data.recipient_number || "");
  const [appSettingsId, setAppSettingsId] = useState(
    data.app_settings_id || ""
  );
  const [appSettings, setAppSettings] = useState<AppSetting[]>([]);
  const [isLoadingAppSettings, setIsLoadingAppSettings] = useState(false);
  const [isCreateSettingOpen, setIsCreateSettingOpen] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setName(data.name);
      setMessage(data.message || "");
      setToNumber(data.recipient_number || "");
      setAppSettingsId(data.app_settings_id || "");

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

  const handleSave = () => {
    onUpdate({
      ...data,
      name,
      message: textMsg,
      recipient_number: toNumber,
      app_settings_id: appSettingsId || undefined,
    });
    onClose();
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
        data={{
          ...data,
          name,
          message: textMsg,
          recipient_number: toNumber,
        }}
      >
        <div className="space-y-2">
          <Label htmlFor="name">Tool Name</Label>
          <Input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., WhatsApp Message"
            className="w-full"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="app-settings-id">Configuration Vars (Optional)</Label>
          <Select
            value={appSettingsId || ""}
            onValueChange={(value) => {
              if (value === "__create__") {
                setIsCreateSettingOpen(true);
                return;
              }
              setAppSettingsId(value || "");
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
            value={toNumber}
            onChange={(e) => setToNumber(e.target.value)}
            placeholder="e.g., 15551234567"
            className="w-full"
          />
          <p className="text-xs text-gray-500">
            Include the country code in the phone number. You may use “+”, but
            not “00”.
          </p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="textMsg">Message</Label>
          <DraggableInput
            id="textMsg"
            value={textMsg}
            onChange={(e) => setMessage(e.target.value)}
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
          if (created?.id) setAppSettingsId(created.id);
        }}
      />
    </>
  );
};
