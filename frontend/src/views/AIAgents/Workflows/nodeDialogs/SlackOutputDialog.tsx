import React, { useState, useEffect } from "react";
import { SlackOutputNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Save } from "lucide-react";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { DraggableInput } from "../components/custom/DraggableInput";
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

type SlackOutputDialogProps = BaseNodeDialogProps<
  SlackOutputNodeData,
  SlackOutputNodeData
>;

export const SlackOutputDialog: React.FC<SlackOutputDialogProps> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;
  const [name, setName] = useState(data.name);
  const [channel, setChannel] = useState(data.channel || "");
  const [message, setMessage] = useState(data.message || "");
  const [appSettingsId, setAppSettingsId] = useState(
    data.app_settings_id || ""
  );
  const [appSettings, setAppSettings] = useState<AppSetting[]>([]);
  const [isLoadingAppSettings, setIsLoadingAppSettings] = useState(false);
  const [isCreateSettingOpen, setIsCreateSettingOpen] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setName(data.name);
      setChannel(data.channel || "");
      setMessage(data.message || "");
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
      channel,
      message,
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
          channel,
          message,
          app_settings_id: appSettingsId || undefined,
        }}
      >
        <div className="space-y-2">
          <Label htmlFor="name">Name</Label>
          <Input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., Slack Message"
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
                    settingTypeLower === "slack" && setting.is_active === 1
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
          <Label htmlFor="channel">Channel ID</Label>
          <DraggableInput
            id="channel"
            value={channel}
            onChange={(e) => setChannel(e.target.value)}
            placeholder="e.g., C12345678 or user@example.com"
            className="w-full break-all"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="message">Message</Label>
          <DraggableInput
            id="message"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="e.g., Hello, how are you?"
            className="w-full"
          />
        </div>
      </NodeConfigPanel>
      <AppSettingDialog
        isOpen={isCreateSettingOpen}
        onOpenChange={setIsCreateSettingOpen}
        mode="create"
        initialType="Slack"
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
