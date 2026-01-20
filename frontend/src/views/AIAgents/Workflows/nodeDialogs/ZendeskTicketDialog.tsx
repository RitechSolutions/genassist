import React, { useState, useEffect } from "react";
import { ZendeskTicketNodeData } from "../types/nodes";
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
import { DraggableTextArea } from "../components/custom/DraggableTextArea";

type ZendeskTicketDialogProps = BaseNodeDialogProps<
  ZendeskTicketNodeData,
  ZendeskTicketNodeData
>;

export const ZendeskTicketDialog: React.FC<ZendeskTicketDialogProps> = (
  props
) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const [name, setName] = useState(data.name || "");
  const [subject, setSubject] = useState(data.subject || "");
  const [description, setDescription] = useState(data.description || "");
  const [requesterName, setRequesterName] = useState(data.requester_name || "");
  const [requesterEmail, setRequesterEmail] = useState(
    data.requester_email || ""
  );
  const [tagsCsv, setTagsCsv] = useState((data.tags || []).join(", "));
  const [appSettingsId, setAppSettingsId] = useState(
    data.app_settings_id || ""
  );
  const [appSettings, setAppSettings] = useState<AppSetting[]>([]);
  const [isLoadingAppSettings, setIsLoadingAppSettings] = useState(false);
  const [isCreateSettingOpen, setIsCreateSettingOpen] = useState(false);

  const getTagsArr = () => {
    return tagsCsv
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
  };

  useEffect(() => {
    if (isOpen) {
      setName(data.name || "");
      setSubject(data.subject || "");
      setDescription(data.description || "");
      setRequesterName(data.requester_name || "");
      setRequesterEmail(data.requester_email || "");
      setTagsCsv((data.tags || []).join(", "));

      setAppSettingsId(data.app_settings_id || "");

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
      subject,
      description,
      requester_name: requesterName,
      requester_email: requesterEmail,
      tags: getTagsArr(),
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
        data={
          {
            ...data,
            name,
            subject,
            description,
            requester_name: requesterName,
            requester_email: requesterEmail,
            tags: getTagsArr(),
            app_settings_id: appSettingsId || undefined,
          } as ZendeskTicketNodeData
        }
      >
        <div className="space-y-2">
          <Label htmlFor="node-name">Node Name</Label>
          <Input
            id="node-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Enter the name of this node"
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
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="Enter ticket subject"
                className="w-full"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <DraggableTextArea
                id="description"
                rows={4}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Enter the issue or request description"
                className="w-full resize-none"
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
                value={requesterName}
                onChange={(e) => setRequesterName(e.target.value)}
                placeholder="e.g., Alice Smith"
                className="w-full"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="requester_email">Requester Email</Label>
              <DraggableInput
                id="requester_email"
                type="email"
                value={requesterEmail}
                onChange={(e) => setRequesterEmail(e.target.value)}
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
                value={tagsCsv}
                onChange={(e) => setTagsCsv(e.target.value)}
                placeholder="e.g., support, urgent, follow-up"
                className="w-full"
              />
            </div>
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
          if (created?.id) setAppSettingsId(created.id);
        }}
      />
    </>
  );
};
