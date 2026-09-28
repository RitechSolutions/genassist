import { useEffect, useState } from "react";
import { JiraNodeData } from "../types/nodes";
import { BaseNodeDialogProps } from "./base";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { Button } from "@/components/button";
import { RichInput } from "@/components/richInput";
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
import { useNodeDialogState } from "./useNodeDialogState";

type JiraDialogProps = BaseNodeDialogProps<JiraNodeData, JiraNodeData>;

export const JiraDialog: React.FC<JiraDialogProps> = (props) => {
  const { isOpen, onClose, data } = props;

  const { values, setField, merged, handleSave } = useNodeDialogState(
    props,
    () => ({
      name: data.name,
      spaceKey: data.spaceKey || "",
      taskName: data.taskName || "",
      taskDescription: data.taskDescription || "",
      app_settings_id: data.app_settings_id || "",
    }),
    (v) => ({
      name: v.name,
      spaceKey: v.spaceKey,
      taskName: v.taskName,
      taskDescription: v.taskDescription,
      app_settings_id: v.app_settings_id || undefined,
    })
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
            placeholder="Enter tool name"
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
            value={values.spaceKey}
            onChange={(e) => setField("spaceKey", e.target.value)}
            placeholder="Enter project name"
            className="w-full"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="name">Task Name</Label>
          <DraggableInput
            id="task_name"
            value={values.taskName}
            onChange={(e) => setField("taskName", e.target.value)}
            placeholder="Enter task name"
            className="w-full"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="name">Task Description</Label>
          <DraggableTextArea
            id="task_description"
            size="body"
            value={values.taskDescription}
            onChange={(e) => setField("taskDescription", e.target.value)}
            placeholder="Enter task description"
            className="w-full"
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
          if (created?.id) setField("app_settings_id", created.id);
        }}
      />
    </>
  );
};
