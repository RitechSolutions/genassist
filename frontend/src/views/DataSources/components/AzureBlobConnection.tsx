import { useState } from "react";
import { Alert, AlertDescription } from "@/components/alert";
import { Badge } from "@/components/badge";
import { Cloud, AlertCircle, CheckCircle, Loader2, Server } from "lucide-react";
import { toast } from "react-hot-toast";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Button } from "@/components/button";
import { DataSource } from "@/interfaces/dataSource.interface";
import { AzureConnection, listBlobs } from "@/services/azureBlobService";

interface AzureBlobConnectionProps {
  dataSource?: DataSource;
  dataSourceName: string;
  connectionData: Record<string, string | number | boolean>;
  onConnectionDataChange: (field: string, value: string | number | boolean) => void;
}

export function AzureBlobConnection({
  dataSourceName,
  connectionData,
  onConnectionDataChange,
}: AzureBlobConnectionProps) {
  const [isTesting, setIsTesting] = useState(false);

  const isConnected = connectionData?.connection_status === "connected";
  const hasError = connectionData?.connection_status === "error";

  const handleTestConnection = async () => {
    if (!dataSourceName.trim()) {
      toast.error("Data source name is required.");
      return;
    }

    if (!connectionData.connectionstring || !connectionData.container) {
      toast.error("Connection String and Container Name are required.");
      return;
    }

    setIsTesting(true);

    try {
      await listBlobs({
        connectionstring: connectionData.connectionstring as string,
        container: connectionData.container as string,
      });

      toast.success("Azure Blob connection test succeeded!");
      onConnectionDataChange("connection_status", "connected");
      onConnectionDataChange("connection_success", true);
    } catch (error) {
      toast.error("Azure Blob connection test failed. Please verify your settings.");
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
          <CheckCircle className="w-3 h-3 mr-1" /> Connected
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
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Cloud className="w-5 h-5 text-blue-600" />
          <span className="font-medium">Azure Blob Storage Configuration</span>
        </div>
        {getStatusBadge()}
      </div>

      {!isConnected && (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {hasError
              ? "Last connection attempt failed. Please verify your settings."
              : "Please test your connection before saving."}
          </AlertDescription>
        </Alert>
      )}

      {/* Connection String */}
      <div className="space-y-1">
        <Label htmlFor="connectionstring">Connection String <span className="text-red-500">*</span></Label>
        <Input
          id="connectionstring"
          type="password"
          placeholder="DefaultEndpointsProtocol=https;AccountName=..."
          value={(connectionData.connectionstring as string) || ""}
          onChange={(e) => onConnectionDataChange("connectionstring", e.target.value)}
        />
      </div>

      {/* Container */}
      <div className="space-y-1">
        <Label htmlFor="container">Container Name <span className="text-red-500">*</span></Label>
        <Input
          id="container"
          type="text"
          placeholder="e.g., my-container"
          value={(connectionData.container as string) || ""}
          onChange={(e) => onConnectionDataChange("container", e.target.value)}
        />
      </div>

      {/* Test Button */}
      <Button
        type="button"
        onClick={handleTestConnection}
        disabled={isTesting}
        className="w-full"
      >
        {isTesting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
        <Server className="mr-2 h-4 w-4" />
        Test Connection
      </Button>
    </div>
  );
}
