// Office365Connection.tsx
import { useEffect, useState } from "react";
import { Button } from "@/components/button";
import { Alert, AlertDescription } from "@/components/alert";
import { Badge } from "@/components/badge";
import { Label } from "@/components/label";
import { Mail, AlertCircle, CheckCircle, Loader2 } from "lucide-react";
import { toast } from "react-hot-toast";
import {
  createTempOffice365DataSource,
  buildOffice365OAuthUrl,
} from "@/services/dataSources";
import { DataSource } from "@/interfaces/dataSource.interface";
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

interface Office365ConnectionProps {
  dataSource?: DataSource;
  dataSourceName: string;
  onDataSourceCreated?: (id: string) => void;
}

export function Office365Connection({
  dataSource,
  dataSourceName,
  onDataSourceCreated,
}: Office365ConnectionProps) {
  const [appSettingsId, setAppSettingsId] = useState(
    (dataSource?.connection_data.app_settings_id as string) || ""
  );
  const [appSettings, setAppSettings] = useState<AppSetting[]>([]);
  const [isLoadingAppSettings, setIsLoadingAppSettings] = useState(false);
  const [isCreateSettingOpen, setIsCreateSettingOpen] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);

  const isConnected = dataSource?.connection_data.user_email;
  const isPending = dataSource?.oauth_status === "pending";
  const hasError = dataSource?.oauth_status === "error";

  const fetchAppSettings = async () => {
    setIsLoadingAppSettings(true);
    try {
      const settings = await getAllAppSettings();
      const filteredSettings = settings.filter((setting) => {
        const settingTypeLower = setting.type.toLowerCase();
        return settingTypeLower === "microsoft" && setting.is_active === 1;
      });
      setAppSettings(filteredSettings);
    } catch (error) {
      console.error("Error fetching app settings:", error);
    } finally {
      setIsLoadingAppSettings(false);
    }
  };

  useEffect(() => {
    setAppSettingsId(
      (dataSource?.connection_data.app_settings_id as string) || ""
    );

    fetchAppSettings();
  }, [dataSource]);

  const handleConnect = async () => {
    if (!dataSourceName.trim()) {
      toast.error("Data source name is required.");
      return;
    }

    if (!appSettingsId) {
      toast.error("Configuration variables are required.");
      return;
    }

    setIsConnecting(true);
    try {
      const selectedAppSettings = appSettings.find(
        (setting) => setting.id === appSettingsId
      );
      const clientId = selectedAppSettings?.values?.microsoft_client_id;
      const tenantId = selectedAppSettings?.values?.microsoft_tenant_id;
      let datasourceId = dataSource?.id;

      if (!datasourceId) {
        datasourceId = await createTempOffice365DataSource(
          dataSourceName,
          appSettingsId
        );
        onDataSourceCreated?.(datasourceId);
      }

      const oauthUrl = buildOffice365OAuthUrl(clientId, tenantId, datasourceId);
      window.location.href = oauthUrl;
    } catch (error) {
      toast.error("Failed to initiate Office 365 connection.");
    } finally {
      setIsConnecting(false);
    }
  };

  const getStatusBadge = () => {
    if (isConnected) {
      return (
        <Badge variant="default" className="text-green-700 bg-green-100">
          <CheckCircle className="w-3 h-3 mr-1" /> Connected
        </Badge>
      );
    }
    if (isPending) {
      return (
        <Badge variant="secondary">
          <Loader2 className="w-3 h-3 mr-1 animate-spin" /> Pending
        </Badge>
      );
    }
    if (hasError) {
      return (
        <Badge variant="destructive">
          <AlertCircle className="w-3 h-3 mr-1" /> Error
        </Badge>
      );
    }
    return (
      <Badge variant="outline">
        <AlertCircle className="w-3 h-3 mr-1" /> Not Connected
      </Badge>
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Mail className="w-5 h-5 text-blue-600" />
          <span className="font-medium">Office365 Connection</span>
        </div>
        {getStatusBadge()}
      </div>

      {isConnected && dataSource?.connection_data?.user_email && (
        <Alert>
          <CheckCircle className="h-4 w-4" />
          <AlertDescription>
            Connected to Office365 account:{" "}
            <strong>{dataSource.connection_data.user_email}</strong>
          </AlertDescription>
        </Alert>
      )}

      {!isConnected && (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {hasError
              ? "Please reauthorize Office365 access before saving."
              : "Please authorize Office365 access before saving."}
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
              setAppSettingsId(value);
            }
          }}
          disabled={isLoadingAppSettings}
        >
          <SelectTrigger id="config_vars">
            <SelectValue placeholder="Select configuration vars" />
          </SelectTrigger>
          <SelectContent>
            {appSettings.map((setting) => (
              <SelectItem key={setting.id} value={setting.id}>
                {setting.name}
              </SelectItem>
            ))}
            <CreateNewSelectItem />
          </SelectContent>
        </Select>
      </div>

      <Button
        type="button"
        onClick={handleConnect}
        disabled={isConnecting}
        variant={isConnected ? "outline" : "default"}
        className="w-full"
      >
        {isConnecting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
        <Mail className="mr-2 h-4 w-4" />
        {isConnected ? "Reauthorize Office365" : "Connect Office365"}
      </Button>

      <AppSettingDialog
        isOpen={isCreateSettingOpen}
        onOpenChange={setIsCreateSettingOpen}
        mode="create"
        initialType="Microsoft"
        disableTypeSelect
        onSettingSaved={async (created) => {
          if (created) {
            await fetchAppSettings();
            setTimeout(() => {
              setAppSettingsId(created.id);
            }, 0);
          }
        }}
      />
    </div>
  );
}
