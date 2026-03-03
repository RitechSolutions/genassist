import { useState, useEffect } from "react";
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
  testConnection,
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
import { AlertCircle, CheckCircle, Loader2, Plug } from "lucide-react";
import { Alert, AlertDescription } from "@/components/alert";
import { Badge } from "@/components/badge";
import {
  DataSource,
  DataSourceConfig,
} from "@/interfaces/dataSource.interface";
import { useQuery } from "@tanstack/react-query";
import { GmailConnection } from "./GmailConnection";
import { Office365Connection } from "./Office365Connection";
import { SchemaFormRenderer } from "@/components/SchemaFormRenderer";

interface DataSourceDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onDataSourceSaved: (createdOrUpdated?: DataSource) => void;
  dataSourceToEdit?: DataSource | null;
  mode?: "create" | "edit";
  defaultSourceType?: string;
  disableSourceType?: boolean;
}

export function DataSourceDialog({
  isOpen,
  onOpenChange,
  onDataSourceSaved,
  dataSourceToEdit = null,
  mode = "create",
  defaultSourceType,
  disableSourceType = false,
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
  const [isTesting, setIsTesting] = useState(false);
  const [testStatus, setTestStatus] = useState<{
    success: boolean;
    message: string;
  } | null>(null);

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
    setTestStatus(null);
  };

  const populateFormWithDataSource = (dataSource: DataSource) => {
    setDataSourceId(dataSource.id);
    setName(dataSource.name);
    setSourceType(dataSource.source_type);
    setConnectionData(dataSource.connection_data);
    setIsActive(dataSource.is_active === 1);
  };

  const getSchemaDefaults = (
    type: string,
  ): Record<string, string | number | boolean> => {
    const schema = dataSourceSchemas[type];
    if (!schema) return {};
    const defaults: Record<string, string | number | boolean> = {};
    for (const field of schema.fields) {
      if (field.default !== undefined && field.default !== null) {
        defaults[field.name] = field.default;
      }
    }
    return defaults;
  };

  const handleConnectionDataChange = (
    fieldName: string,
    value: string | number | boolean,
  ) => {
    setConnectionData((prev) => ({ ...prev, [fieldName]: value }));
  };

  const handleTestConnection = async () => {
    setIsTesting(true);
    setTestStatus(null);
    try {
      const result = await testConnection(
        sourceType,
        connectionData,
        dataSourceId,
      );
      setTestStatus(result);
    } catch {
      setTestStatus({ success: false, message: "Test failed." });
    } finally {
      setIsTesting(false);
    }
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
          } access before saving.`,
        );
        return;
      }
    } else {
      const schema = dataSourceSchemas?.[sourceType];
      if (!schema) {
        toast.error(
          "Schema not loaded yet. Please wait a moment and try again.",
        );
        return;
      }

      const isFieldVisible = (field: {
        conditional?: { field: string; value: string | number | boolean };
      }) => {
        if (!field.conditional) return true;
        return (
          connectionData[field.conditional.field] === field.conditional.value
        );
      };

      const schemaMissing = schema.fields
        .filter(
          (field) =>
            field.required &&
            isFieldVisible(field) &&
            (connectionData[field.name] === undefined ||
              connectionData[field.name] === null ||
              connectionData[field.name] === ""),
        )
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

  const isOAuthType = ["gmail", "o365"].includes(sourceType);
  const schema = dataSourceSchemas[sourceType];
  const hasAdvancedFields = schema?.fields.some((f) => !f.required) ?? false;

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
            {/* Section 1: Name + Source Type */}
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
                    setConnectionData(getSchemaDefaults(value));
                    setTestStatus(null);
                    setShowAdvanced(false);
                  }}
                >
                  <SelectTrigger
                    className="w-full"
                    disabled={disableSourceType}
                  >
                    <SelectValue placeholder="Select Source Type" />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(dataSourceSchemas).map(([type, schema]) => (
                      <SelectItem key={type} value={type}>
                        {schema.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>

            {/* Section 2: Fields */}
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

                {/* Regular (non-advanced) fields */}
                {!isOAuthType && schema && (
                  <SchemaFormRenderer
                    schema={schema}
                    connectionData={connectionData}
                    onChange={handleConnectionDataChange}
                    showAdvanced={false}
                  />
                )}

                {/* Active + Advanced toggles */}
                <div className="flex items-center gap-2 border-t pt-4">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="is_active">Active</Label>
                    <Switch
                      id="is_active"
                      checked={isActive}
                      onCheckedChange={setIsActive}
                    />
                  </div>
                  <div className="flex-1" />
                  {!isOAuthType && hasAdvancedFields && (
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

                {/* Advanced fields (below toggles) */}
                {!isOAuthType && showAdvanced && schema?.fields && (
                  <SchemaFormRenderer
                    schema={schema as DataSourceConfig}
                    connectionData={connectionData}
                    onChange={handleConnectionDataChange}
                    showAdvanced={true}
                    advancedOnly
                  />
                )}

                {/* Test Connection */}
                {!isOAuthType && (
                  <div className="space-y-2">
                    <Button
                      type="button"
                      className="w-full"
                      onClick={handleTestConnection}
                      disabled={isTesting}
                    >
                      {isTesting ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <Plug className="mr-2 h-4 w-4" />
                      )}
                      Test Connection
                    </Button>
                    <div className="flex justify-end">
                      {testStatus?.success === true ? (
                        <Badge
                          variant="default"
                          className="text-green-700 bg-green-100"
                        >
                          <CheckCircle className="w-3 h-3 mr-1" /> Connected
                        </Badge>
                      ) : testStatus?.success === false ? (
                        <Badge variant="destructive">
                          <AlertCircle className="w-3 h-3 mr-1" /> Error
                        </Badge>
                      ) : (
                        <Badge variant="outline">
                          <AlertCircle className="w-3 h-3 mr-1" /> Not Connected
                        </Badge>
                      )}
                    </div>
                    {isTesting ? (
                      <Alert>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <AlertDescription>
                          Testing connection, please wait…
                        </AlertDescription>
                      </Alert>
                    ) : testStatus?.success === true ? (
                      <Alert variant="success">
                        <CheckCircle className="h-4 w-4" />
                        <AlertDescription>
                          {testStatus.message}
                        </AlertDescription>
                      </Alert>
                    ) : testStatus?.success === false ? (
                      <Alert variant="destructive">
                        <AlertCircle className="h-4 w-4" />
                        <AlertDescription>
                          Connection failed. Please verify your settings.
                          {testStatus.message && (
                            <span className="block mt-1 text-xs opacity-75">
                              {testStatus.message}
                            </span>
                          )}
                        </AlertDescription>
                      </Alert>
                    ) : (
                      <Alert>
                        <AlertCircle className="h-4 w-4" />
                        <AlertDescription>
                          Please test your connection before saving.
                        </AlertDescription>
                      </Alert>
                    )}
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
