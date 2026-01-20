import { useState, useEffect, useMemo } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import {
  createDataSource,
  getDataSourceFormSchemas,
  updateDataSource,
  getDataSource,
} from "@/services/dataSources";
import { Switch } from "@/components/switch";
import { Label } from "@/components/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { toast } from "react-hot-toast";
import { Loader2 } from "lucide-react";
import { DataSource, DataSourceField } from "@/interfaces/dataSource.interface";
import { useQuery } from "@tanstack/react-query";
import { GmailConnection } from "./GmailConnection";
import { Office365Connection } from "./Office365Connection";
import { SmbShareFolderConnection } from "./SmbShareFolderConnection";
import { AzureBlobConnection } from "./AzureBlobConnection";

interface DataSourceDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onDataSourceSaved: (createdOrUpdated?: DataSource) => void;
  dataSourceToEdit?: DataSource | null;
  mode?: "create" | "edit";
  defaultSourceType?: string;
}

export function DataSourceDialog({
  isOpen,
  onOpenChange,
  onDataSourceSaved,
  dataSourceToEdit = null,
  mode = "create",
  defaultSourceType,
}: DataSourceDialogProps) {
  const [name, setName] = useState("");
  const [sourceType, setSourceType] = useState("");
  const [connectionData, setConnectionData] = useState<
    Record<string, string | number | boolean>
  >({});
  const [isActive, setIsActive] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [dataSourceId, setDataSourceId] = useState<string | undefined>("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [currentDataSource, setCurrentDataSource] = useState<
    DataSource | undefined
  >();

  const { data, isLoading: isLoadingConfig } = useQuery({
    queryKey: ["dataSourceSchemas"],
    queryFn: () => getDataSourceFormSchemas(),
    refetchInterval: isOpen ? 5000 : false,
    refetchOnWindowFocus: false,
    staleTime: 3000,
  });

  const dataSourceSchemas = data ?? {};

  useEffect(() => {
    const initializeForm = async () => {
      if (isOpen) {
        resetForm();
        if (mode === "create" && defaultSourceType) {
          setSourceType(defaultSourceType);
        }
        if (dataSourceToEdit && mode === "edit") {
          if (
            ["gmail", "o365"].includes(dataSourceToEdit.source_type) &&
            dataSourceToEdit.id
          ) {
            try {
              const latestData = await getDataSource(dataSourceToEdit.id);
              if (latestData) {
                setCurrentDataSource(latestData);
                populateFormWithDataSource(latestData);
              } else {
                setCurrentDataSource(dataSourceToEdit);
                populateFormWithDataSource(dataSourceToEdit);
              }
            } catch (error) {
              setCurrentDataSource(dataSourceToEdit);
              populateFormWithDataSource(dataSourceToEdit);
            }
          } else {
            setCurrentDataSource(dataSourceToEdit);
            populateFormWithDataSource(dataSourceToEdit);
          }
        } else {
          setCurrentDataSource(undefined);
        }
      }
    };

    initializeForm();
  }, [isOpen, dataSourceToEdit, mode]);

  const resetForm = () => {
    setDataSourceId(undefined);
    setName("");
    setSourceType("");
    setConnectionData({});
    setIsActive(true);
    setShowAdvanced(false);
  };

  const populateFormWithDataSource = (dataSource: DataSource) => {
    setDataSourceId(dataSource.id);
    setName(dataSource.name);
    setSourceType(dataSource.source_type);
    setConnectionData(dataSource.connection_data);
    setIsActive(dataSource.is_active === 1);
  };

  const handleConnectionDataChange = (
    field: DataSourceField,
    value: string | number
  ) => {
    setConnectionData((prev) => ({
      ...prev,
      [field.name]: value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const missingFields: string[] = [];

    if (!name) missingFields.push("Name");
    if (!sourceType) missingFields.push("Source Type");

    if (missingFields.length > 0) {
      if (missingFields.length === 1) {
        toast.error(`${missingFields[0]} is required.`);
      } else {
        toast.error(`Please provide: ${missingFields.join(", ")}.`);
      }
      return;
    }

    if (["gmail", "o365"].includes(sourceType)) {
      const oauthDataSource =
        currentDataSource ||
        ({
          id: dataSourceId,
          oauth_status: "disconnected",
          name,
          source_type: sourceType,
          connection_data: connectionData,
          is_active: 0,
        } as DataSource);

      if (oauthDataSource.oauth_status !== "connected") {
        toast.error(
          `Please authorize ${
            sourceType === "o365" ? "Office 365" : "Gmail"
          } access before saving.`
        );
        return;
      }
    } else {
      const schema = dataSourceSchemas?.[sourceType];
      if (!schema) {
        // Allow creation for known manual integrations even if schema is missing
        if (["smb_share_folder"].includes(sourceType)) {
          const useLocalFs = Boolean(connectionData.use_local_fs);

          if (useLocalFs) {
            if (!connectionData.local_root) {
              toast.error(
                "Local Root Path is required when using Local Filesystem."
              );
              return;
            }
          } else {
            if (!connectionData.smb_host) {
              toast.error(
                "SMB Host is required when not using Local Filesystem."
              );
              return;
            }
            if (!connectionData.smb_share) {
              toast.error(
                "SMB Share Name is required when not using Local Filesystem."
              );
              return;
            }
          }
        } else if (["azure_blob"].includes(sourceType)) {
          if (!connectionData.connectionstring || !connectionData.container) {
            toast.error(
              "ConnectionString and Container Name are required when using Azure Blob"
            );
            return;
          }
        } else {
          toast.error(
            "Schema not loaded yet. Please wait a moment and try again."
          );
          return;
        }
      } else {
        // Normal schema validation
        const schemaMissing = schema.fields
          .filter((field) => field.required && !connectionData[field.name])
          .map((field) => field.label);

        if (schemaMissing.length > 0) {
          if (schemaMissing.length === 1) {
            toast.error(`${schemaMissing[0]} is required.`);
          } else {
            toast.error(`Please provide: ${schemaMissing.join(", ")}.`);
          }
          return;
        }
      }
    }

    setIsSubmitting(true);
    try {
      const data: Partial<DataSource> = {
        name,
        source_type: sourceType,
        connection_data: connectionData,
        is_active: isActive ? 1 : 0,
      };

      if (mode === "create") {
        if (["gmail", "o365"].includes(sourceType) && dataSourceId) {
          const updated = await updateDataSource(dataSourceId, data);
          toast.success("Data source updated successfully.");
          onDataSourceSaved(updated);
        } else {
          const created = await createDataSource(data as DataSource);
          toast.success("Data source created successfully.");
          onDataSourceSaved(created);
        }
      } else {
        if (!dataSourceId) throw new Error("Missing data source ID");
        const updated = await updateDataSource(dataSourceId, data);
        toast.success("Data source updated successfully.");
        onDataSourceSaved(updated);
      }

      onOpenChange(false);
      resetForm();
    } catch (error) {
      toast.error(`Failed to ${mode} data source.`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderField = (field: DataSourceField) => {
    const value = connectionData[field.name] ?? field.default;

    switch (field.type) {
      case "select":
        return (
          <Select
            value={value as string}
            onValueChange={(val) => handleConnectionDataChange(field, val)}
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder={`Select ${field.label}`} />
            </SelectTrigger>
            <SelectContent>
              {field.options?.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        );
      case "number":
        return (
          <Input
            type="number"
            value={value as number}
            onChange={(e) =>
              handleConnectionDataChange(field, parseFloat(e.target.value))
            }
            // min={field.min}
            // max={field.max}
            // step={field.step}
            placeholder={field.label}
          />
        );
      case "password":
        return (
          <Input
            type="password"
            value={value as string}
            onChange={(e) => handleConnectionDataChange(field, e.target.value)}
            placeholder={field.label}
          />
        );
      default:
        return (
          <Input
            type="text"
            value={value as string}
            onChange={(e) => handleConnectionDataChange(field, e.target.value)}
            placeholder={field.placeholder || field.label}
          />
        );
    }
  };

  const requiredFields =
    dataSourceSchemas[sourceType]?.fields.filter((f) => f.required) ?? [];
  const optionalFields =
    dataSourceSchemas[sourceType]?.fields.filter((f) => !f.required) ?? [];

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px] p-0 overflow-hidden">
        <form
          onSubmit={handleSubmit}
          className="max-h-[90vh] overflow-y-auto overflow-x-hidden flex flex-col"
        >
          <DialogHeader className="p-6 pb-4">
            <DialogTitle>
              {mode === "create" ? "Create Data Source" : "Edit Data Source"}
            </DialogTitle>
          </DialogHeader>

          <div className="px-6 pb-6 space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Name"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="source_type">Source Type</Label>
              {isLoadingConfig ? (
                <div className="flex items-center justify-center p-4">
                  <Loader2 className="w-6 h-6 animate-spin" />
                </div>
              ) : (
                <Select
                  value={sourceType}
                  onValueChange={(value) => {
                    setSourceType(value);
                    setConnectionData({});
                  }}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select Source Type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem key="gmail" value="gmail">
                      Gmail
                    </SelectItem>
                    <SelectItem key="o365" value="o365">
                      Office365
                    </SelectItem>
                    <SelectItem key="smb_share_folder" value="smb_share_folder">
                      Network Share/Folder
                    </SelectItem>
                    <SelectItem key="azure_blob" value="azure_blob">
                      Azure Blob Storage
                    </SelectItem>
                    {Object.entries(dataSourceSchemas).map(([type, schema]) => (
                      <SelectItem key={type} value={type}>
                        {schema.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>

            {sourceType && (
              <>
                {sourceType === "gmail" && (
                  <GmailConnection
                    dataSource={
                      currentDataSource ||
                      (dataSourceId
                        ? ({
                            id: dataSourceId,
                            oauth_status: "disconnected",
                            name,
                            source_type: sourceType,
                            connection_data: connectionData,
                            is_active: 0,
                          } as DataSource)
                        : undefined)
                    }
                    dataSourceName={name}
                    onDataSourceCreated={(id) => setDataSourceId(id)}
                  />
                )}
                {sourceType === "o365" && (
                  <Office365Connection
                    dataSource={
                      currentDataSource ||
                      (dataSourceId
                        ? ({
                            id: dataSourceId,
                            oauth_status: "disconnected",
                            name,
                            source_type: sourceType,
                            connection_data: connectionData,
                            is_active: 0,
                          } as DataSource)
                        : undefined)
                    }
                    dataSourceName={name}
                    onDataSourceCreated={(id) => setDataSourceId(id)}
                  />
                )}
                {sourceType === "smb_share_folder" && (
                  <SmbShareFolderConnection
                    dataSource={
                      currentDataSource ||
                      (dataSourceId
                        ? ({
                            id: dataSourceId,
                            name,
                            source_type: sourceType,
                            connection_data: connectionData,
                            is_active: 0,
                          } as DataSource)
                        : undefined)
                    }
                    dataSourceName={name}
                    connectionData={connectionData ?? {}}
                    onConnectionDataChange={(field, value) =>
                      setConnectionData((prev) => ({ ...prev, [field]: value }))
                    }
                  />
                )}
                {sourceType === "azure_blob" && (
                  <AzureBlobConnection
                    dataSourceName={name}
                    connectionData={connectionData ?? {}}
                    onConnectionDataChange={(field, value) =>
                      setConnectionData((prev) => ({ ...prev, [field]: value }))
                    }
                  />
                )}

                {!["gmail", "o365", "smb_share_folder"].includes(sourceType) && (
                  <div className="space-y-4">
                    {requiredFields.map((field) => (
                      <div key={field.name} className="space-y-2">
                        <Label htmlFor={field.name}>
                          {field.label}
                          {field.required && (
                            <span className="text-red-500 ml-1">*</span>
                          )}
                        </Label>
                        {renderField(field)}
                        {field.description && (
                          <p className="text-sm text-muted-foreground">
                            {field.description}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                <div className="flex items-center justify-between pt-4 border-t">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="is_active">Active</Label>
                    <Switch
                      id="is_active"
                      checked={isActive}
                      onCheckedChange={setIsActive}
                    />
                  </div>
                  {optionalFields.length > 0 && (
                    <div className="flex items-center gap-2">
                      <Label htmlFor="show_advanced">Advanced</Label>
                      <Switch
                        id="show_advanced"
                        checked={showAdvanced}
                        onCheckedChange={setShowAdvanced}
                      />
                    </div>
                  )}
                </div>

                {showAdvanced && (
                  <div className="space-y-4">
                    {optionalFields.map((field) => (
                      <div key={field.name} className="space-y-2">
                        <Label htmlFor={field.name}>{field.label}</Label>
                        {renderField(field)}
                        {field.description && (
                          <p className="text-sm text-muted-foreground">
                            {field.description}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>

          <DialogFooter className="px-6 py-4 border-t">
            <div className="flex justify-end gap-3 w-full">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                {mode === "create" ? "Create" : "Update"}
              </Button>
            </div>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
