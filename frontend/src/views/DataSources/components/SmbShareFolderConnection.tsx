import { useState } from "react";
import { Alert, AlertDescription } from "@/components/alert";
import { Badge } from "@/components/badge";
import { Folder, AlertCircle, CheckCircle, Loader2, Server } from "lucide-react";
import { toast } from "react-hot-toast";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Switch } from "@/components/switch";
import { Button } from "@/components/button";
import { DataSource } from "@/interfaces/dataSource.interface";
import { listDirectory } from "@/services/smbShareFolderService";


interface SmbShareFolderConnectionProps {
  dataSource?: DataSource;
  dataSourceName: string;
  connectionData: Record<string, string | number | boolean>;
  onConnectionDataChange: (field: string, value: string | number | boolean) => void;
}

export function SmbShareFolderConnection({
  dataSource,
  dataSourceName,
  connectionData,
  onConnectionDataChange,
}: SmbShareFolderConnectionProps) {
  const [isTesting, setIsTesting] = useState(false);

  const isConnected = connectionData?.connection_status === "connected";
  const hasError = connectionData?.connection_status === "error";
  const useLocalFS = Boolean(connectionData.use_local_fs);

  const handleTestConnection = async () => {
    if (!dataSourceName.trim()) {
      toast.error("Data source name is required.");
      return;
    }

    // Conditional validation logic
    if (useLocalFS) {
      if (!connectionData.local_root) {
        toast.error("Local Root Path is required when using Local Filesystem.");
        return;
      }
    } else {
      if (!connectionData.smb_host || !connectionData.smb_share) {
        toast.error("SMB Host and SMB Share Name are required when not using Local Filesystem.");
        return;
      }
    }

    setIsTesting(true);
    try {
        // Build connection parameters for listDirectory
        const params = {
        smb_host: connectionData.smb_host as string,
        smb_share: connectionData.smb_share as string,
        smb_user: connectionData.smb_user as string,
        smb_pass: connectionData.smb_pass as string,
        smb_port: Number(connectionData.smb_port) || 445,
        use_local_fs: Boolean(connectionData.use_local_fs),
        local_root: connectionData.local_root as string,
        subpath: "", // root directory
        only_files: false,
        only_dirs: false,
        };

        // Call the API
        const result = await listDirectory(params);

      toast.success("SMB connection test succeeded!");
      onConnectionDataChange("connection_status", "connected");
      onConnectionDataChange("connection_success", true); // mimic GmailConnection pattern
    } catch (error) {
      toast.error("SMB connection test failed. Please verify your settings.");
      onConnectionDataChange("connection_status", "error");
      onConnectionDataChange("connection_success", false);
    } finally {
      setIsTesting(false);
    }
  };

  const getStatusBadge = () => {
    if (isConnected) {
      return (
        <Badge variant="default" className="text-green-700 bg-green-100">
          <CheckCircle className="w-3 h-3 mr-1" />
          Connected
        </Badge>
      );
    }
    if (hasError) {
      return (
        <Badge variant="destructive">
          <AlertCircle className="w-3 h-3 mr-1" />
          Error
        </Badge>
      );
    }
    return (
      <Badge variant="outline">
        <AlertCircle className="w-3 h-3 mr-1" />
        Not Connected
      </Badge>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Folder className="w-5 h-5 text-blue-600" />
          <span className="font-medium">Network Share / Folder Configuration</span>
        </div>
        {getStatusBadge()}
      </div>

      {/* Connection info / warning */}
      {!isConnected && (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {hasError
              ? "Last connection attempt failed. Please verify your SMB settings."
              : "Please test your connection before saving."}
          </AlertDescription>
        </Alert>
      )}

      {/* SMB Host + Port */}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1">
          <Label htmlFor="smb_host">
            SMB Host {!useLocalFS && <span className="text-red-500">*</span>}
          </Label>
          <Input
            id="smb_host"
            type="text"
            placeholder="e.g., 192.168.1.10 or fileserver.local"
            value={(connectionData.smb_host as string) || ""}
            onChange={(e) => onConnectionDataChange("smb_host", e.target.value)}
            disabled={useLocalFS}
          />
          <p className="text-sm text-muted-foreground">
            Hostname or IP address of the SMB server.
          </p>
        </div>

        <div className="space-y-1">
          <Label htmlFor="smb_port">SMB Port</Label>
          <Input
            id="smb_port"
            type="number"
            placeholder="e.g., 445"
            value={(connectionData.smb_port as number) || ""}
            onChange={(e) => onConnectionDataChange("smb_port", Number(e.target.value))}
            disabled={useLocalFS}
          />
          <p className="text-sm text-muted-foreground">Defaults to 445 if not specified.</p>
        </div>
      </div>

      {/* SMB Share */}
      <div className="space-y-1">
        <Label htmlFor="smb_share">
          SMB Share Name {!useLocalFS && <span className="text-red-500">*</span>}
        </Label>
        <Input
          id="smb_share"
          type="text"
          placeholder="e.g., shared"
          value={(connectionData.smb_share as string) || ""}
          onChange={(e) => onConnectionDataChange("smb_share", e.target.value)}
          disabled={useLocalFS}
        />
        <p className="text-sm text-muted-foreground">
          The name of the SMB share you want to access.
        </p>
      </div>

      {/* Username + Password */}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1">
          <Label htmlFor="smb_user">SMB Username</Label>
          <Input
            id="smb_user"
            type="text"
            placeholder="e.g., DOMAIN\\username"
            value={(connectionData.smb_user as string) || ""}
            onChange={(e) => onConnectionDataChange("smb_user", e.target.value)}
            disabled={useLocalFS}
          />
        </div>

        <div className="space-y-1">
          <Label htmlFor="smb_pass">SMB Password</Label>
          <Input
            id="smb_pass"
            type="password"
            placeholder="••••••••"
            value={(connectionData.smb_pass as string) || ""}
            onChange={(e) => onConnectionDataChange("smb_pass", e.target.value)}
            disabled={useLocalFS}
          />
        </div>
      </div>

      {/* Local FS Toggle + Root Path */}
      <div className="grid grid-cols-2 gap-4 items-end">
        <div className="flex items-center gap-2">
          <Switch
            id="use_local_fs"
            checked={useLocalFS}
            onCheckedChange={(checked) => onConnectionDataChange("use_local_fs", checked)}
          />
          <Label htmlFor="use_local_fs" className="cursor-pointer">
            Use Local Filesystem
          </Label>
        </div>

        <div className="space-y-1">
          <Label htmlFor="local_root">
            Local Root Path {useLocalFS && <span className="text-red-500">*</span>}
          </Label>
          <Input
            id="local_root"
            type="text"
            placeholder="/mnt/data/shared-folder or C:\\shared"
            value={(connectionData.local_root as string) || ""}
            onChange={(e) => onConnectionDataChange("local_root", e.target.value)}
            required={useLocalFS}
          />
        </div>
      </div>

      {/* Test Connection Button */}
      <Button
        type="button"
        onClick={handleTestConnection}
        disabled={isTesting}
        variant="default"
        className="w-full"
      >
        {isTesting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
        <Server className="mr-2 h-4 w-4" />
        Test Connection
      </Button>
    </div>
  );
}
