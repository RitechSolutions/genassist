import { useEffect, useState } from "react";
import { JiraNodeData } from "../types/nodes";
import { BaseNodeDialogProps } from "./base";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Save } from "lucide-react";
import { DraggableInput } from "../components/custom/DraggableInput";
import { DraggableTextArea } from "../components/custom/DraggableTextArea";
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

type JiraDialogProps = BaseNodeDialogProps<JiraNodeData, JiraNodeData>;

export const JiraDialog: React.FC<JiraDialogProps> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;
  const [name, setName] = useState(data.name);
  const [spaceKey, setSpaceKey] = useState(data.spaceKey || "");
  const [taskName, setTaskName] = useState(data.taskName || "");
  const [taskDescription, setTaskDescription] = useState(
    data.taskDescription || ""
  );
  const [appSettingsId, setAppSettingsId] = useState(
    data.app_settings_id || ""
  );
  const [appSettings, setAppSettings] = useState<AppSetting[]>([]);
  const [isLoadingAppSettings, setIsLoadingAppSettings] = useState(false);
  const [isCreateSettingOpen, setIsCreateSettingOpen] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setName(data.name);
      setSpaceKey(data.spaceKey || "");
      setTaskName(data.taskName || "");
      setTaskDescription(data.taskDescription || "");

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
      spaceKey,
      taskName,
      taskDescription,
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
          spaceKey,
          taskName,
          taskDescription,
          app_settings_id: appSettingsId || undefined,
        }}
      >
        <div className="space-y-2">
          <Label htmlFor="name">Tool Name</Label>
          <Input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Enter tool name"
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
                  return settingTypeLower === "jira" && setting.is_active === 1;
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
          <Label htmlFor="name">Space Key</Label>
          <DraggableInput
            id="space_key"
            value={spaceKey}
            onChange={(e) => setSpaceKey(e.target.value)}
            placeholder="Enter project name"
            className="w-full"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="name">Task Name</Label>
          <DraggableInput
            id="task_name"
            value={taskName}
            onChange={(e) => setTaskName(e.target.value)}
            placeholder="Enter task name"
            className="w-full"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="name">Task Description</Label>
          <DraggableTextArea
            id="task_description"
            rows={6}
            value={taskDescription}
            onChange={(e) => setTaskDescription(e.target.value)}
            placeholder="Enter task description"
            className="w-full resize-none"
          />
        </div>
      </NodeConfigPanel>
      <AppSettingDialog
        isOpen={isCreateSettingOpen}
        onOpenChange={setIsCreateSettingOpen}
        mode="create"
        initialType="Jira"
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
