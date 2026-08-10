import { useState, useEffect, useMemo } from "react";
import { Input } from "@/components/ui/input";
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
import { SalesforceConnection } from "./SalesforceConnection";
import { SchemaFormRenderer } from "@/components/SchemaFormRenderer";
import { CRUDDialog } from "@/components/ui/crud-dialog";
import { FormField } from "@/components/ui/form-field";

interface DataSourceDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onDataSourceSaved: (createdOrUpdated?: DataSource) => void;
  dataSourceToEdit?: DataSource | null;
  mode?: "create" | "edit";
  defaultSourceType?: string;
  disableSourceType?: boolean;
}

/**
 * The dialog owns these form values (CRUDDialog<T>). `connectionData` mirrors
 * how the original tracked all per-type fields — a single dynamic map keyed by
 * field name — rather than a discrete key per data-source type.
 */
type DataSourceFormValues = {
  name: string;
  sourceType: string;
  connectionData: Record<string, ConnectionDataValue>;
  isActive: boolean;
  dataSourceId: string | undefined;
};

export function DataSourceDialog({
  isOpen,
  onOpenChange,
  onDataSourceSaved,
  dataSourceToEdit = null,
  mode = "create",
  defaultSourceType,
  disableSourceType = false,
}: DataSourceDialogProps) {
  // Extra (non-form) state stays in the component body — never inside the
  // CRUDDialog `children` render prop.
  const [currentDataSource, setCurrentDataSource] = useState<
    DataSource | undefined
  >();
  // Body-level mirror of the selected source type, kept in sync with the
  // CRUDDialog-owned `sourceType` form value. It drives whether the header
  // shows the General/Advanced tab bar (that decision is made here, outside
  // the render prop, so it needs the type at the component-body level).
  const [selectedSourceType, setSelectedSourceType] = useState<string>("");
  const [isTesting, setIsTesting] = useState(false);
  const [testStatus, setTestStatus] = useState<ConnectionStatus | null>(null);
  const [testedConnectionData, setTestedConnectionData] = useState<Record<
    string,
    ConnectionDataValue
  > | null>(null);
  // Bumped once the edited source (possibly fetched async for OAuth types) is
  // ready, so CRUDDialog re-initializes the form values from it via `resetKey`.
  const [formResetToken, setFormResetToken] = useState(0);

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

  // Initialize the extra body state when the dialog opens (mirrors the original
  // `initializeForm` / `populateFormWithDataSource`). The form VALUES are owned
  // by CRUDDialog and derived from `currentDataSource` below.
  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;

    const resetExtraState = () => {
      setSelectedSourceType("");
      setTestStatus(null);
      setTestedConnectionData(null);
    };

    const populateExtraState = (dataSource: DataSource) => {
      setSelectedSourceType(dataSource.source_type.toLowerCase());
      setTestStatus(dataSource.connection_status ?? null);
      setTestedConnectionData(
        dataSource.connection_status
          ? structuredClone(dataSource.connection_data)
          : null,
      );
    };

    const initializeForm = async () => {
      resetExtraState();
      if (dataSourceToEdit && mode === "edit") {
        if (
          ["gmail", "o365"].includes(dataSourceToEdit.source_type) &&
          dataSourceToEdit.id
        ) {
          try {
            const latestData = await getDataSource(dataSourceToEdit.id);
            if (cancelled) return;
            const source = latestData ?? dataSourceToEdit;
            setCurrentDataSource(source);
            populateExtraState(source);
          } catch (error) {
            if (cancelled) return;
            setCurrentDataSource(dataSourceToEdit);
            populateExtraState(dataSourceToEdit);
          }
        } else {
          setCurrentDataSource(dataSourceToEdit);
          populateExtraState(dataSourceToEdit);
        }
        if (!cancelled) setFormResetToken((t) => t + 1);
      } else {
        setCurrentDataSource(undefined);
        setSelectedSourceType(defaultSourceType?.toLowerCase() ?? "");
      }
    };

    initializeForm();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, dataSourceToEdit, mode]);

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

  const handleTestConnection = async (
    sourceType: string,
    connectionData: Record<string, ConnectionDataValue>,
    dataSourceId: string | undefined,
  ) => {
    setIsTesting(true);
    setTestStatus(null);
    try {
      const result = await testDataSourceConnection(
        sourceType,
        connectionData,
        dataSourceId,
      );
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

  // Use the freshly loaded source when it matches the entity being edited,
  // otherwise fall back to the passed-in `dataSourceToEdit`.
  const editSource =
    currentDataSource &&
    dataSourceToEdit &&
    currentDataSource.id === dataSourceToEdit.id
      ? currentDataSource
      : dataSourceToEdit;

  // Whether the selected source type exposes advanced (optional) schema fields —
  // the condition under which the header shows the General/Advanced tab bar (the
  // equivalent of the old inline "Advanced" toggle's visibility, and analogous
  // to LLMProvider's `hasOptionalFields`). OAuth and Salesforce types never
  // render the schema-driven advanced fields.
  const selectedSchema = dataSourceSchemas[selectedSourceType];
  const isOAuthSourceType = ["gmail", "o365"].includes(selectedSourceType);
  const isSalesforceSourceType = selectedSourceType === "salesforce";
  const hasAdvancedContent =
    !isOAuthSourceType &&
    !isSalesforceSourceType &&
    (selectedSchema?.fields.some((f) => !f.required) ?? false);

  return (
    <CRUDDialog<DataSourceFormValues>
      open={isOpen}
      onOpenChange={onOpenChange}
      mode={mode}
      maxWidth="500px"
      bodyClassName="space-y-4"
      resetKey={formResetToken}
      tabs={
        hasAdvancedContent
          ? [
              { value: "general", label: "General" },
              { value: "advanced", label: "Advanced" },
            ]
          : undefined
      }
      initialValues={{
        name: "",
        sourceType:
          mode === "create" ? defaultSourceType?.toLowerCase() ?? "" : "",
        connectionData: {},
        isActive: true,
        dataSourceId: undefined,
      }}
      editValues={
        dataSourceToEdit
          ? {
              name: editSource.name,
              sourceType: editSource.source_type.toLowerCase(),
              connectionData: editSource.connection_data,
              isActive: editSource.is_active === 1,
              dataSourceId: editSource.id,
            }
          : null
      }
      title={{ create: "Create Data Source", edit: "Edit Data Source" }}
      submitLabel={{ create: "Create", edit: "Update" }}
      loadingLabel={{ create: "Create", edit: "Update" }}
      successMessage={(values, m) =>
        m === "create"
          ? ["gmail", "o365"].includes(values.sourceType) && values.dataSourceId
            ? "Data source updated successfully."
            : "Data source created successfully."
          : "Data source updated successfully."
      }
      errorMessage={(_err, m) => `Failed to ${m} data source.`}
      validate={(values) => {
        const missingFields: string[] = [];

        if (!values.name) missingFields.push("Name");
        if (!values.sourceType) missingFields.push("Source Type");

        if (missingFields.length > 0) {
          if (missingFields.length === 1) {
            toast.error(`${missingFields[0]} is required.`);
          } else {
            toast.error(`Please provide: ${missingFields.join(", ")}.`);
          }
          return { name: "invalid" };
        }

        if (
          values.sourceType === "salesforce" &&
          !values.connectionData.app_settings_id
        ) {
          toast.error("Configuration Vars are required.");
          return { connectionData: "invalid" };
        }

        if (["gmail", "o365"].includes(values.sourceType)) {
          const oauthDataSource =
            currentDataSource ||
            ({
              id: values.dataSourceId,
              oauth_status: "disconnected",
              name: values.name,
              source_type: values.sourceType,
              connection_data: values.connectionData,
              is_active: 0,
            } as DataSource);

          if (oauthDataSource.oauth_status !== "connected") {
            toast.error(
              `Please authorize ${
                values.sourceType === "o365" ? "Office 365" : "Gmail"
              } access before saving.`,
            );
            return { connectionData: "invalid" };
          }
        } else {
          const schema = dataSourceSchemas?.[values.sourceType];
          if (!schema) {
            toast.error(
              "Schema not loaded yet. Please wait a moment and try again.",
            );
            return { sourceType: "invalid" };
          }

          const isFieldVisible = (field: {
            conditional?: { field: string; value: string | number | boolean };
          }) => {
            if (!field.conditional) return true;
            return (
              values.connectionData[field.conditional.field] ===
              field.conditional.value
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
                isConnectionValueEmpty(field, values.connectionData[field.name]),
            )
            .map((field) => field.label);

          if (schemaMissing.length > 0) {
            if (schemaMissing.length === 1) {
              toast.error(`${schemaMissing[0]} is required.`);
            } else {
              toast.error(`Please provide: ${schemaMissing.join(", ")}.`);
            }
            return { connectionData: "invalid" };
          }
        }

        return null;
      }}
      onSubmit={async (values, { mode: m }) => {
        const hasChangedSinceTest =
          testStatus !== null &&
          testedConnectionData !== null &&
          JSON.stringify(values.connectionData) !==
            JSON.stringify(testedConnectionData);

        const payload: Partial<DataSource> = {
          name: values.name,
          source_type: values.sourceType,
          connection_data: values.connectionData,
          connection_status: hasChangedSinceTest
            ? undefined
            : testStatus ?? undefined,
          is_active: values.isActive ? 1 : 0,
        };

        if (m === "create") {
          if (
            ["gmail", "o365"].includes(values.sourceType) &&
            values.dataSourceId
          ) {
            const updated = await updateDataSource(
              values.dataSourceId,
              payload,
            );
            onDataSourceSaved(updated);
          } else {
            const created = await createDataSource(payload as DataSource);
            onDataSourceSaved(created);
          }
        } else {
          if (!values.dataSourceId) throw new Error("Missing data source ID");
          const updated = await updateDataSource(values.dataSourceId, payload);
          onDataSourceSaved(updated);
        }
      }}
    >
      {({ values, setField, activeTab }) => {
        const sourceType = values.sourceType;
        const connectionData = values.connectionData;
        const isOAuthType = ["gmail", "o365"].includes(sourceType);
        const isSalesforce = sourceType === "salesforce";
        const schema = dataSourceSchemas[sourceType];

        const hasChangedSinceTest =
          testStatus !== null &&
          testedConnectionData !== null &&
          JSON.stringify(connectionData) !==
            JSON.stringify(testedConnectionData);

        const handleConnectionDataChange = (
          fieldName: string,
          value: ConnectionDataValue,
        ) => {
          setField("connectionData", { ...connectionData, [fieldName]: value });
        };

        return (
          <>
            {/* General tab */}
            <div className={activeTab === "advanced" ? "hidden" : "space-y-4"}>
              {/* Name */}
              <FormField id="name" label="Name">
                <Input
                  id="name"
                  value={values.name}
                  onChange={(e) => setField("name", e.target.value)}
                  placeholder="Name"
                />
              </FormField>

              {/* Source Type */}
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
                      setField("sourceType", value.toLowerCase());
                      setField("connectionData", getSchemaDefaults(value));
                      setTestStatus(null);
                      setTestedConnectionData(null);
                      setSelectedSourceType(value.toLowerCase());
                    }}
                  >
                    <SelectTrigger
                      className="w-full"
                      disabled={disableSourceType}
                    >
                      <SelectValue placeholder="Select Source Type" />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.entries(dataSourceSchemas).map(
                        ([type, schema]) => (
                          <SelectItem key={type} value={type}>
                            {schema.name}
                          </SelectItem>
                        ),
                      )}
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
                        (values.dataSourceId
                          ? ({
                              id: values.dataSourceId,
                              oauth_status: 'disconnected',
                              name: values.name,
                              source_type: sourceType,
                              connection_data: connectionData,
                              is_active: 0,
                            } as DataSource)
                          : undefined)
                      }
                      dataSourceName={values.name}
                      onDataSourceCreated={(id) => setField("dataSourceId", id)}
                    />
                  )}

                  {sourceType === 'o365' && (
                    <Office365Connection
                      dataSource={
                        currentDataSource ||
                        (values.dataSourceId
                          ? ({
                              id: values.dataSourceId,
                              oauth_status: 'disconnected',
                              name: values.name,
                              source_type: sourceType,
                              connection_data: connectionData,
                              is_active: 0,
                            } as DataSource)
                          : undefined)
                      }
                      dataSourceName={values.name}
                      onDataSourceCreated={(id) => setField("dataSourceId", id)}
                    />
                  )}

                  {isSalesforce && (
                    <SalesforceConnection
                      connectionData={connectionData}
                      onChange={handleConnectionDataChange}
                    />
                  )}

                  {/* Required fields */}
                  {!isOAuthType && !isSalesforce && schema?.fields && (
                    <SchemaFormRenderer
                      schema={{ fields: schema.fields }}
                      connectionData={connectionData}
                      onChange={handleConnectionDataChange}
                      showAdvanced={false}
                    />
                  )}

                  {/* Active toggle */}
                  <div className="flex items-center gap-2 border-t pt-4">
                    <Label htmlFor="is_active">Active</Label>
                    <Switch
                      id="is_active"
                      checked={values.isActive}
                      onCheckedChange={(checked) =>
                        setField("isActive", checked)
                      }
                    />
                  </div>

                  {/* Test connection */}
                  {!isOAuthType && (
                    <ConnectionTestPanel
                      isTesting={isTesting}
                      testStatus={testStatus}
                      hasChangedSinceTest={hasChangedSinceTest}
                      onTest={() =>
                        handleTestConnection(
                          sourceType,
                          connectionData,
                          values.dataSourceId,
                        )
                      }
                    />
                  )}
                </>
              )}
            </div>

            {/* Advanced tab */}
            {hasAdvancedContent && schema?.fields && (
              <div
                className={activeTab === "advanced" ? "space-y-4" : "hidden"}
              >
                <SchemaFormRenderer
                  schema={{ fields: schema.fields }}
                  connectionData={connectionData}
                  onChange={handleConnectionDataChange}
                  showAdvanced={true}
                  advancedOnly
                />
              </div>
            )}
          </>
        );
      }}
    </CRUDDialog>
  );
}
