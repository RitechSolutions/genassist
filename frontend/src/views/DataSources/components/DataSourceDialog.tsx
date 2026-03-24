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
  testDataSourceConnection,
} from '@/services/dataSources';
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
import { ConnectionTestPanel } from "@/components/ConnectionTestPanel";
import type { ConnectionStatus } from "@/interfaces/connectionStatus.interface";
import {
  ConnectionDataValue,
  DataSource,
  DataSourceField,
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
    Record<string, ConnectionDataValue>
  >({});
  const [isActive, setIsActive] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [dataSourceId, setDataSourceId] = useState<string | undefined>("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [currentDataSource, setCurrentDataSource] = useState<
    DataSource | undefined
  >();
  const [isTesting, setIsTesting] = useState(false);
  const [testStatus, setTestStatus] = useState<ConnectionStatus | null>(null);
  const [testedConnectionData, setTestedConnectionData] = useState<Record<
    string,
    ConnectionDataValue
  > | null>(null);

  const { data, isLoading: isLoadingConfig } = useQuery({
    queryKey: ["dataSourceSchemas"],
    queryFn: () => getDataSourceFormSchemas(),
    refetchOnWindowFocus: false,
  });

  const dataSourceSchemas = useMemo(() => {
    if (!data) return {};

    return Object.fromEntries(
      Object.entries(data).map(([key, value]) => [key.toLowerCase(), value]),
    );
  }, [data]);

  useEffect(() => {
    const initializeForm = async () => {
      if (isOpen) {
        resetForm();
        if (mode === "create" && defaultSourceType) {
          setSourceType(defaultSourceType.toLowerCase() as string);
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
    setTestedConnectionData(null);
  };

  const populateFormWithDataSource = (dataSource: DataSource) => {
    setDataSourceId(dataSource.id);
    setName(dataSource.name);
    setSourceType(dataSource.source_type.toLowerCase() as string);
    setConnectionData(dataSource.connection_data);
    setIsActive(dataSource.is_active === 1);
    setTestStatus(dataSource.connection_status ?? null);
    setTestedConnectionData(dataSource.connection_status ? structuredClone(dataSource.connection_data) : null);
  };

  const getSchemaDefaults = (
    type: string,
  ): Record<string, ConnectionDataValue> => {
    const schema = dataSourceSchemas[type];
    if (!schema) return {};
    const defaults: Record<string, ConnectionDataValue> = {};
    for (const field of schema.fields) {
      if (field.default !== undefined && field.default !== null) {
        defaults[field.name] = field.default;
      }
    }
    return defaults;
  };

  const handleConnectionDataChange = (
    fieldName: string,
    value: ConnectionDataValue,
  ) => {
    setConnectionData((prev) => ({ ...prev, [fieldName]: value }));
  };

  const handleTestConnection = async () => {
    setIsTesting(true);
    setTestStatus(null);
    try {
      const result = await testDataSourceConnection(sourceType, connectionData, dataSourceId);
      setTestStatus({
        status: result.success ? "Connected" : "Error",
        last_tested_at: new Date().toISOString(),
        message: result.message,
      });
      setTestedConnectionData(structuredClone(connectionData));
    } catch {
      setTestStatus({
        status: "Error",
        last_tested_at: new Date().toISOString(),
        message: "Test failed.",
      });
      setTestedConnectionData(structuredClone(connectionData));
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

      const isConnectionValueEmpty = (
        field: DataSourceField,
        v: ConnectionDataValue | undefined,
      ): boolean => {
        if (v === undefined || v === null || v === "") return true;
        if (field.type === "tags" && Array.isArray(v) && v.length === 0) {
          return true;
        }
        return false;
      };

      const schemaMissing = schema.fields
        .filter(
          (field) =>
            field.required &&
            isFieldVisible(field) &&
            isConnectionValueEmpty(field, connectionData[field.name]),
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
        connection_status: hasChangedSinceTest ? undefined : (testStatus ?? undefined),
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
  const hasChangedSinceTest =
    testStatus !== null &&
    testedConnectionData !== null &&
    JSON.stringify(connectionData) !== JSON.stringify(testedConnectionData);

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px] p-0 overflow-hidden">
        <form onSubmit={handleSubmit} className="max-h-[90vh] overflow-y-auto overflow-x-hidden flex flex-col">
          <DialogHeader className="p-6 pb-4">
            <DialogTitle>{mode === 'create' ? 'Create Data Source' : 'Edit Data Source'}</DialogTitle>
          </DialogHeader>

          <div className="px-6 pb-6 space-y-4">
            {/* Name & Source Type */}
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" />
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
                    setSourceType(value.toLowerCase() as string);
                    setConnectionData(getSchemaDefaults(value));
                    setTestStatus(null);
                    setTestedConnectionData(null);
                    setShowAdvanced(false);
                  }}
                >
                  <SelectTrigger className="w-full" disabled={disableSourceType}>
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

            {sourceType && (
              <>
                {sourceType === 'gmail' && (
                  <GmailConnection
                    dataSource={
                      currentDataSource ||
                      (dataSourceId
                        ? ({
                            id: dataSourceId,
                            oauth_status: 'disconnected',
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

                {sourceType === 'o365' && (
                  <Office365Connection
                    dataSource={
                      currentDataSource ||
                      (dataSourceId
                        ? ({
                            id: dataSourceId,
                            oauth_status: 'disconnected',
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

                {/* Required fields */}
                {!isOAuthType && schema?.fields && (
                  <SchemaFormRenderer
                    schema={{ fields: schema.fields }}
                    connectionData={connectionData}
                    onChange={handleConnectionDataChange}
                    showAdvanced={false}
                  />
                )}

                {/* Active & Advanced toggles */}
                <div className="flex items-center gap-2 border-t pt-4">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="is_active">Active</Label>
                    <Switch id="is_active" checked={isActive} onCheckedChange={setIsActive} />
                  </div>
                  <div className="flex-1" />
                  {!isOAuthType && hasAdvancedFields && (
                    <div className="flex items-center gap-2">
                      <Label htmlFor="show_advanced">Advanced</Label>
                      <Switch id="show_advanced" checked={showAdvanced} onCheckedChange={setShowAdvanced} />
                    </div>
                  )}
                </div>

                {/* Advanced fields */}
                {!isOAuthType && showAdvanced && schema?.fields && (
                  <SchemaFormRenderer
                    schema={{ fields: schema.fields }}
                    connectionData={connectionData}
                    onChange={handleConnectionDataChange}
                    showAdvanced={true}
                    advancedOnly
                  />
                )}

                {/* Test connection */}
                {!isOAuthType && (
                  <ConnectionTestPanel
                    isTesting={isTesting}
                    testStatus={testStatus}
                    hasChangedSinceTest={hasChangedSinceTest}
                    onTest={handleTestConnection}
                  />
                )}
              </>
            )}
          </div>

          <DialogFooter className="px-6 py-4 border-t">
            <div className="flex justify-end gap-3 w-full">
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
                Cancel
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {mode === 'create' ? 'Create' : 'Update'}
              </Button>
            </div>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
