import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/label";
import { Switch } from "@/components/switch";
import { Loader2 } from "lucide-react";
import {
  createLLMProvider,
  getLLMProvidersFormSchemas,
  testLLMProviderConnection,
  updateLLMProvider,
} from "@/services/llmProviders";
import { LLMProvider } from "@/interfaces/llmProvider.interface";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/select";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ConnectionTestPanel } from "@/components/ConnectionTestPanel";
import type { ConnectionStatus } from "@/interfaces/connectionStatus.interface";
import { SchemaFormRenderer } from "@/components/SchemaFormRenderer";
import { FormField } from "@/components/ui/form-field";
import { CRUDDialog } from "@/components/ui/crud-dialog";

/**
 * Error whose message should be surfaced verbatim by the dialog (required-field
 * checks and the data-residency block that can't be expressed as inline field
 * errors because they target component-body state rather than form values).
 */
class SubmitError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SubmitError";
  }
}

interface LLMProviderDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onProviderSaved: (provider?: LLMProvider) => void;
  onProviderUpdated?: (provider: LLMProvider) => void;
  providerToEdit?: LLMProvider | null;
  mode?: "create" | "edit";
}

type LLMProviderFormValues = {
  name: string;
  is_active: boolean;
};

export function LLMProviderDialog({
  isOpen,
  onOpenChange,
  onProviderSaved,
  onProviderUpdated,
  providerToEdit = null,
  mode = "create",
}: LLMProviderDialogProps) {
  const [providerId, setProviderId] = useState<string | undefined>(
    providerToEdit?.id
  );
  const [llmType, setLlmType] = useState<string>(
    providerToEdit?.llm_model_provider ?? ""
  );
  const [llmModel, setLlmModel] = useState<string>(
    providerToEdit?.llm_model ?? ""
  );

  const [connectionData, setConnectionData] = useState<
    Record<string, string | number | string[]>
  >(providerToEdit?.connection_data ?? {});

  const [isTesting, setIsTesting] = useState(false);
  const [testStatus, setTestStatus] = useState<ConnectionStatus | null>(null);
  const [testedConnectionData, setTestedConnectionData] = useState<Record<
    string,
    string | number | string[]
  > | null>(null);
  const queryClient = useQueryClient();

  const { data, isLoading: isLoadingConfig } = useQuery({
    queryKey: ["supportedModels", isOpen],
    queryFn: () => getLLMProvidersFormSchemas(),
    refetchOnWindowFocus: false,
    enabled: isOpen,
    staleTime: 0,
  });

  const supportedModels = data ?? {};

  useEffect(() => {
    if (isOpen) {
      if (providerToEdit) {
        setProviderId(providerToEdit.id);
        setLlmType(providerToEdit.llm_model_provider);
        setLlmModel(providerToEdit.llm_model);
        setConnectionData(providerToEdit.connection_data);
        setTestStatus(providerToEdit.connection_status ?? null);
        setTestedConnectionData(
          providerToEdit.connection_status
            ? structuredClone(providerToEdit.connection_data)
            : null
        );
      } else {
        resetForm();
      }
    }
  }, [isOpen, providerToEdit]);

  useEffect(() => {
    if (llmType && supportedModels[llmType]) {
      setConnectionData((prev) => {
        const defaultValues = supportedModels[llmType].fields.reduce(
          (acc, field) => {
            if (field.default !== undefined && !prev[field.name]) {
              acc[field.name] = field.default as string | number | string[];
            }
            return acc;
          },
          {} as Record<string, string | number | string[]>
        );

        if (Object.keys(defaultValues).length > 0) {
          if (defaultValues.model) {
            setLlmModel(defaultValues.model.toString());
          }
          return { ...prev, ...defaultValues };
        }
        return prev;
      });
    }
  }, [llmType, supportedModels]);

  const resetForm = () => {
    setProviderId(undefined);
    setLlmType("");
    setConnectionData({});
    setTestStatus(null);
    setTestedConnectionData(null);
  };

  const handleConnectionDataChange = (
    fieldName: string,
    value: string | number | string[]
  ) => {
    if (fieldName === "model") {
      setLlmModel(value as string);
    }
    setConnectionData((prev) => ({
      ...prev,
      [fieldName]: value,
    }));
  };

  const handleTestConnection = async () => {
    setIsTesting(true);
    setTestStatus(null);
    try {
      const result = await testLLMProviderConnection(
        llmType,
        connectionData,
        providerId
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

  const hasOptionalFields =
    (supportedModels[llmType]?.fields.filter((f) => !f.required) ?? []).length >
    0;

  const hasChangedSinceTest =
    testStatus !== null &&
    testedConnectionData !== null &&
    JSON.stringify(connectionData) !== JSON.stringify(testedConnectionData);

  return (
    <CRUDDialog<LLMProviderFormValues>
      open={isOpen}
      onOpenChange={onOpenChange}
      mode={mode}
      maxWidth="500px"
      resetKey={providerToEdit?.id ?? null}
      tabs={
        hasOptionalFields
          ? [
              { value: "general", label: "General" },
              { value: "advanced", label: "Advanced" },
            ]
          : undefined
      }
      initialValues={{ name: "", is_active: true }}
      editValues={
        providerToEdit
          ? {
              name: providerToEdit.name ?? "",
              is_active: providerToEdit.is_active === 1,
            }
          : null
      }
      title={{ create: "Create LLM Provider", edit: "Edit LLM Provider" }}
      submitLabel={{ create: "Create", edit: "Update" }}
      loadingLabel={{ create: "Create", edit: "Update" }}
      successMessage={{
        create: "LLM provider created successfully.",
        edit: "LLM provider updated successfully.",
      }}
      errorMessage={(err, m) =>
        err instanceof SubmitError
          ? err.message
          : `Failed to ${m === "create" ? "create" : "update"} LLM provider.`
      }
      validate={(values) =>
        !values.name.trim() ? { name: "Name is required." } : null
      }
      onSubmit={async (values, { mode: m }) => {
        if (!llmType) {
          throw new SubmitError("Type is required.");
        }

        const providerConfig = supportedModels[llmType];
        if (!providerConfig) {
          throw new SubmitError("Invalid provider type.");
        }

        const missingFields = providerConfig.fields
          .filter((field) => field.required && !connectionData[field.name])
          .map((field) => field.label);

        if (missingFields.length > 0) {
          throw new SubmitError(
            missingFields.length === 1
              ? `${missingFields[0]} is required.`
              : `Please provide: ${missingFields.join(", ")}.`
          );
        }

        const payload = {
          name: values.name,
          llm_model_provider: llmType,
          llm_model: llmModel,
          connection_data: connectionData,
          connection_status: hasChangedSinceTest
            ? undefined
            : (testStatus ?? undefined),
          is_active: values.is_active ? 1 : 0,
        };

        if (m === "create") {
          const created = await createLLMProvider(payload);
          if (!created) {
            throw new SubmitError(
              "LLM provider blocked by the data residency policy. Check the provider's allowed regions."
            );
          }
          queryClient.invalidateQueries({ queryKey: ["llmProviders"] });
          onProviderSaved(created);
        } else {
          if (!providerId) throw new Error("Missing provider ID");
          const updated = await updateLLMProvider(providerId, payload);
          if (!updated) {
            throw new SubmitError(
              "LLM provider blocked by the data residency policy. Check the provider's allowed regions."
            );
          }
          queryClient.invalidateQueries({ queryKey: ["llmProviders"] });
          if (onProviderUpdated) {
            onProviderUpdated(updated);
          }
        }
      }}
      onSuccess={() => resetForm()}
    >
      {({ values, setField, errors, activeTab }) => (
        <>
          {/* General tab */}
          <div className={activeTab === "advanced" ? "hidden" : "space-y-5"}>
            <FormField id="name" label="Name" error={errors.name}>
              <Input
                id="name"
                value={values.name}
                onChange={(e) => setField("name", e.target.value)}
                placeholder="Provider name"
              />
            </FormField>

            <div className="space-y-2">
              <Label htmlFor="llm_type">Type</Label>
              {isLoadingConfig ? (
                <div className="flex items-center justify-center p-4">
                  <Loader2 className="w-6 h-6 animate-spin" />
                </div>
              ) : (
                <Select
                  value={llmType}
                  onValueChange={(value) => {
                    setLlmType(value);
                    setConnectionData({});
                    setTestStatus(null);
                    setTestedConnectionData(null);
                  }}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select LLM Type" />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(supportedModels).map(
                      ([type, providerConfig]) => (
                        <SelectItem key={type} value={type}>
                          {providerConfig.name}
                        </SelectItem>
                      )
                    )}
                  </SelectContent>
                </Select>
              )}
            </div>

            {llmType && supportedModels[llmType] && (
              <>
                <SchemaFormRenderer
                  schema={{ fields: supportedModels[llmType].fields }}
                  connectionData={connectionData}
                  onChange={handleConnectionDataChange}
                  showAdvanced={false}
                />
                <div className="flex items-center gap-2 border-t pt-4">
                  <Label htmlFor="is_active">Active</Label>
                  <Switch
                    id="is_active"
                    checked={values.is_active}
                    onCheckedChange={(checked) => setField("is_active", checked)}
                  />
                </div>
                <ConnectionTestPanel
                  isTesting={isTesting}
                  testStatus={testStatus}
                  hasChangedSinceTest={hasChangedSinceTest}
                  onTest={handleTestConnection}
                />
              </>
            )}
          </div>

          {/* Advanced tab */}
          {llmType && supportedModels[llmType] && hasOptionalFields && (
            <div className={activeTab === "advanced" ? "space-y-5" : "hidden"}>
              <SchemaFormRenderer
                schema={{ fields: supportedModels[llmType].fields }}
                connectionData={connectionData}
                onChange={handleConnectionDataChange}
                showAdvanced={true}
                advancedOnly={true}
              />
            </div>
          )}
        </>
      )}
    </CRUDDialog>
  );
}
