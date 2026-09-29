import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/label";
import { Switch } from "@/components/switch";
import { Loader2 } from "lucide-react";
import {
  createAudioProvider,
  getAudioProviderFormSchemas,
  testAudioProviderConnection,
  updateAudioProvider,
} from "@/services/audioProviders";
import { AudioProvider } from "@/interfaces/audioProvider.interface";
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

const CAPABILITY_OPTIONS = [
  { value: "tts", label: "Text-to-Speech (TTS)" },
  { value: "stt", label: "Speech-to-Text (STT)" },
  { value: "both", label: "Both (TTS + STT)" },
];

/**
 * Error whose message should be surfaced verbatim by the dialog (required-field
 * checks that can't be expressed as inline field errors because they target
 * component-body state rather than form values).
 */
class SubmitError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SubmitError";
  }
}

interface AudioProviderDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onProviderSaved: (provider?: AudioProvider) => void;
  onProviderUpdated?: (provider: AudioProvider) => void;
  providerToEdit?: AudioProvider | null;
  mode?: "create" | "edit";
}

type AudioProviderFormValues = {
  name: string;
  is_active: boolean;
};

export function AudioProviderDialog({
  isOpen,
  onOpenChange,
  onProviderSaved,
  onProviderUpdated,
  providerToEdit = null,
  mode = "create",
}: AudioProviderDialogProps) {
  const [providerId, setProviderId] = useState<string | undefined>(
    providerToEdit?.id
  );
  const [providerType, setProviderType] = useState<string>(
    providerToEdit?.provider_type ?? ""
  );
  const [capability, setCapability] = useState<string>(
    providerToEdit?.capability ?? "both"
  );
  const [connectionData, setConnectionData] = useState<
    Record<string, string | number | string[]>
  >(
    (providerToEdit?.connection_data as Record<
      string,
      string | number | string[]
    >) ?? {}
  );

  const [isTesting, setIsTesting] = useState(false);
  const [testStatus, setTestStatus] = useState<ConnectionStatus | null>(null);
  const [testedConnectionData, setTestedConnectionData] = useState<Record<
    string,
    string | number | string[]
  > | null>(null);
  const queryClient = useQueryClient();

  const { data, isLoading: isLoadingConfig } = useQuery({
    queryKey: ["audioProviderFormSchemas", isOpen],
    queryFn: () => getAudioProviderFormSchemas(),
    refetchOnWindowFocus: false,
    enabled: isOpen,
    staleTime: 0,
  });

  const formSchemas = data ?? {};

  useEffect(() => {
    if (isOpen) {
      if (providerToEdit) {
        setProviderId(providerToEdit.id);
        setProviderType(providerToEdit.provider_type);
        setCapability(providerToEdit.capability);
        setConnectionData(
          (providerToEdit.connection_data as Record<
            string,
            string | number | string[]
          >) ?? {}
        );
        setTestStatus(providerToEdit.connection_status ?? null);
        setTestedConnectionData(
          providerToEdit.connection_status
            ? structuredClone(
                providerToEdit.connection_data as Record<
                  string,
                  string | number | string[]
                >
              )
            : null
        );
      } else {
        resetForm();
      }
    }
  }, [isOpen, providerToEdit]);

  const resetForm = () => {
    setProviderId(undefined);
    setProviderType("");
    setCapability("both");
    setConnectionData({});
    setTestStatus(null);
    setTestedConnectionData(null);
  };

  const handleConnectionDataChange = (
    fieldName: string,
    value: string | number | string[]
  ) => {
    setConnectionData((prev) => ({ ...prev, [fieldName]: value }));
  };

  const handleTestConnection = async () => {
    setIsTesting(true);
    setTestStatus(null);
    try {
      const result = await testAudioProviderConnection(
        providerType,
        capability,
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

  const hasChangedSinceTest =
    testStatus !== null &&
    testedConnectionData !== null &&
    JSON.stringify(connectionData) !== JSON.stringify(testedConnectionData);

  return (
    <CRUDDialog<AudioProviderFormValues>
      open={isOpen}
      onOpenChange={onOpenChange}
      mode={mode}
      maxWidth="500px"
      resetKey={providerToEdit?.id ?? null}
      initialValues={{ name: "", is_active: true }}
      editValues={
        providerToEdit
          ? {
              name: providerToEdit.name ?? "",
              is_active: providerToEdit.is_active === 1,
            }
          : null
      }
      title={{ create: "Create Audio Provider", edit: "Edit Audio Provider" }}
      submitLabel={{ create: "Create", edit: "Update" }}
      loadingLabel={{ create: "Create", edit: "Update" }}
      successMessage={{
        create: "Audio provider created successfully.",
        edit: "Audio provider updated successfully.",
      }}
      errorMessage={(err, m) =>
        err instanceof SubmitError
          ? err.message
          : `Failed to ${m === "create" ? "create" : "update"} audio provider.`
      }
      validate={(values) =>
        !values.name.trim() ? { name: "Name is required." } : null
      }
      onSubmit={async (values, { mode: m }) => {
        const missingFields = [
          !providerType && "Provider Type",
          !capability && "Capability",
        ].filter(Boolean);

        if (missingFields.length > 0) {
          throw new SubmitError(`Please provide: ${missingFields.join(", ")}.`);
        }

        const providerConfig = formSchemas[providerType];
        if (providerConfig) {
          const missingConfigFields = providerConfig.fields
            .filter((f) => f.required && !connectionData[f.name])
            .map((f) => f.label);
          if (missingConfigFields.length > 0) {
            throw new SubmitError(
              `Please provide: ${missingConfigFields.join(", ")}.`
            );
          }
        }

        const payload = {
          name: values.name,
          provider_type: providerType,
          capability,
          connection_data: connectionData,
          connection_status: hasChangedSinceTest
            ? undefined
            : (testStatus ?? undefined),
          is_active: values.is_active ? 1 : 0,
          is_default: 0,
        };

        if (m === "create") {
          const created = await createAudioProvider(payload);
          queryClient.invalidateQueries({ queryKey: ["audioProviders"] });
          onProviderSaved(created);
        } else {
          if (!providerId) throw new Error("Missing provider ID");
          const updated = await updateAudioProvider(providerId, payload);
          queryClient.invalidateQueries({ queryKey: ["audioProviders"] });
          if (onProviderUpdated) onProviderUpdated(updated);
        }
      }}
      onSuccess={() => resetForm()}
    >
      {({ values, setField, errors }) => (
        <>
          <FormField id="name" label="Name" error={errors.name}>
            <Input
              id="name"
              value={values.name}
              onChange={(e) => setField("name", e.target.value)}
              placeholder="Provider name"
            />
          </FormField>

          <div className="space-y-2">
            <Label htmlFor="provider_type">Provider Type</Label>
            {isLoadingConfig ? (
              <div className="flex items-center justify-center p-4">
                <Loader2 className="w-6 h-6 animate-spin" />
              </div>
            ) : (
              <Select
                value={providerType}
                onValueChange={(value) => {
                  setProviderType(value);
                  setConnectionData({});
                  setTestStatus(null);
                  setTestedConnectionData(null);
                }}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select provider type" />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(formSchemas).map(([type, config]) => (
                    <SelectItem key={type} value={type}>
                      {(config.display_name as string | undefined) ||
                        config.name ||
                        type}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="capability">Capability</Label>
            <Select value={capability} onValueChange={setCapability}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select capability" />
              </SelectTrigger>
              <SelectContent>
                {CAPABILITY_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {providerType && formSchemas[providerType] && (
            <>
              <SchemaFormRenderer
                schema={{ fields: formSchemas[providerType].fields }}
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
        </>
      )}
    </CRUDDialog>
  );
}
