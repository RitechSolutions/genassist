import { useEffect, useState } from "react";
import { Alert, AlertDescription } from "@/components/alert";
import { Label } from "@/components/label";
import { Input } from "@/components/ui/input";
import { Cloud, AlertCircle, Loader2 } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { AppSetting } from "@/interfaces/app-setting.interface";
import { getAllAppSettings } from "@/services/appSettings";
import { CreateNewSelectItem } from "@/components/CreateNewSelectItem";
import { AppSettingDialog } from "@/views/AppSettings/components/AppSettingDialog";
import type { ConnectionDataValue } from "@/interfaces/dataSource.interface";

interface SalesforceConnectionProps {
  connectionData: Record<string, ConnectionDataValue>;
  onChange: (fieldName: string, value: ConnectionDataValue) => void;
}

export function SalesforceConnection({
  connectionData,
  onChange,
}: SalesforceConnectionProps) {
  const appSettingsId = (connectionData.app_settings_id as string) || "";
  const contentField = (connectionData.content_field as string) || "";
  const language = (connectionData.language as string) || "";
  const dataCategory = (connectionData.data_category as string) || "";

  const [appSettings, setAppSettings] = useState<AppSetting[]>([]);
  const [isLoadingAppSettings, setIsLoadingAppSettings] = useState(false);
  const [appSettingsError, setAppSettingsError] = useState<string | null>(null);
  const [isCreateSettingOpen, setIsCreateSettingOpen] = useState(false);

  const fetchAppSettings = async () => {
    setIsLoadingAppSettings(true);
    setAppSettingsError(null);
    try {
      const settings = await getAllAppSettings();
      const filteredSettings = settings.filter((setting) => {
        const settingTypeLower = setting.type.toLowerCase();
        return settingTypeLower === "salesforce" && setting.is_active === 1;
      });
      setAppSettings(filteredSettings);
    } catch (error) {
      console.error("Error fetching app settings:", error);
      setAppSettingsError("Failed to load configuration vars.");
    } finally {
      setIsLoadingAppSettings(false);
    }
  };

  useEffect(() => {
    fetchAppSettings();
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Cloud className="w-5 h-5 text-blue-600" />
        <span className="font-medium">SalesForce Connection</span>
      </div>

      {!appSettingsId && (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Select the SalesForce configuration vars to connect. Credentials are
            managed in App Settings, not entered here.
          </AlertDescription>
        </Alert>
      )}

      {/* Configuration Vars */}
      <div className="space-y-1">
        <Label htmlFor="config_vars">
          Configuration Vars <span className="text-red-500">*</span>
        </Label>
        <Select
          value={appSettingsId || ""}
          onValueChange={(value) => {
            if (value === "__create__") {
              setIsCreateSettingOpen(true);
            } else {
              onChange("app_settings_id", value);
            }
          }}
          disabled={isLoadingAppSettings}
        >
          <SelectTrigger id="config_vars">
            <SelectValue
              placeholder={
                isLoadingAppSettings
                  ? "Loading configuration vars..."
                  : "Select configuration vars"
              }
            />
          </SelectTrigger>
          <SelectContent>
            {isLoadingAppSettings ? (
              <div className="flex items-center justify-center gap-2 py-4 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading...
              </div>
            ) : appSettings.length === 0 ? (
              <div className="px-2 py-3 text-sm text-muted-foreground">
                No SalesForce configuration vars found. Create one below.
              </div>
            ) : (
              appSettings.map((setting) => (
                <SelectItem key={setting.id} value={setting.id}>
                  {setting.name}
                </SelectItem>
              ))
            )}
            <CreateNewSelectItem />
          </SelectContent>
        </Select>
        {appSettingsError && (
          <p className="text-xs text-destructive">{appSettingsError}</p>
        )}
      </div>

      {/* Content field (required) */}
      <div className="space-y-1">
        <Label htmlFor="content_field">
          Content Field <span className="text-red-500">*</span>
        </Label>
        <Input
          id="content_field"
          value={contentField}
          onChange={(e) => onChange("content_field", e.target.value)}
          placeholder="e.g. Article_Body__c"
        />
        <p className="text-xs text-muted-foreground">
          The API name of the SalesForce Knowledge article body field to ingest.
        </p>
      </div>

      {/* Advanced filters (optional) */}
      <div className="space-y-1">
        <Label htmlFor="language">Language</Label>
        <Input
          id="language"
          value={language}
          onChange={(e) => onChange("language", e.target.value)}
          placeholder="e.g. en_US (optional)"
        />
      </div>

      <div className="space-y-1">
        <Label htmlFor="data_category">Data Category</Label>
        <Input
          id="data_category"
          value={dataCategory}
          onChange={(e) => onChange("data_category", e.target.value)}
          placeholder="Data category filter (optional)"
        />
      </div>

      <AppSettingDialog
        isOpen={isCreateSettingOpen}
        onOpenChange={setIsCreateSettingOpen}
        mode="create"
        initialType="Salesforce"
        disableTypeSelect
        onSettingSaved={async (created) => {
          if (created) {
            await fetchAppSettings();
            setTimeout(() => {
              onChange("app_settings_id", created.id);
            }, 0);
          }
        }}
      />
    </div>
  );
}
