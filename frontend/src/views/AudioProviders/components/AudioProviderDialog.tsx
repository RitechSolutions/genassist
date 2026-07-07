import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/label";
import { Switch } from "@/components/switch";
import { Button } from "@/components/button";
import { Loader2 } from "lucide-react";
import { toast } from "react-hot-toast";
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

const CAPABILITY_OPTIONS = [
  { value: "tts", label: "Text-to-Speech (TTS)" },
  { value: "stt", label: "Speech-to-Text (STT)" },
  { value: "both", label: "Both (TTS + STT)" },
];

interface AudioProviderDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onProviderSaved: (provider?: AudioProvider) => void;
  onProviderUpdated?: (provider: AudioProvider) => void;
  providerToEdit?: AudioProvider | null;
  mode?: "create" | "edit";
}

export function AudioProviderDialog({
  isOpen,
  onOpenChange,
  onProviderSaved,
  onProviderUpdated,
  providerToEdit = null,
  mode = "create",
}: AudioProviderDialogProps) {
  const [providerId, setProviderId] = useState<string | undefined>(providerToEdit?.id);
  const [name, setName] = useState(providerToEdit?.name ?? "");
  const [providerType, setProviderType] = useState<string>(providerToEdit?.provider_type ?? "");
  const [capability, setCapability] = useState<string>(providerToEdit?.capability ?? "both");
  const [isActive, setIsActive] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [connectionData, setConnectionData] = useState<Record<string, string | number | string[]>>(
    (providerToEdit?.connection_data as Record<string, string | number | string[]>) ?? {}
  );

  const [isTesting, setIsTesting] = useState(false);
  const [testStatus, setTestStatus] = useState<ConnectionStatus | null>(null);
  const [testedConnectionData, setTestedConnectionData] = useState<Record<string, string | number | string[]> | null>(null);
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
        setName(providerToEdit.name);
        setProviderType(providerToEdit.provider_type);
        setCapability(providerToEdit.capability);
        setConnectionData((providerToEdit.connection_data as Record<string, string | number | string[]>) ?? {});
        setIsActive(providerToEdit.is_active === 1);
        setTestStatus(providerToEdit.connection_status ?? null);
        setTestedConnectionData(
          providerToEdit.connection_status
            ? structuredClone(providerToEdit.connection_data as Record<string, string | number | string[]>)
            : null
        );
      } else {
        resetForm();
      }
    }
  }, [isOpen, providerToEdit]);

  const resetForm = () => {
    setProviderId(undefined);
    setName("");
    setProviderType("");
    setCapability("both");
    setConnectionData({});
    setIsActive(true);
    setTestStatus(null);
    setTestedConnectionData(null);
  };

  const handleConnectionDataChange = (fieldName: string, value: string | number | string[]) => {
    setConnectionData((prev) => ({ ...prev, [fieldName]: value }));
  };

  const handleTestConnection = async () => {
    setIsTesting(true);
    setTestStatus(null);
    try {
      const result = await testAudioProviderConnection(providerType, capability, connectionData, providerId);
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

    const missingFields = [
      !name && "Name",
      !providerType && "Provider Type",
      !capability && "Capability",
    ].filter(Boolean);

    if (missingFields.length > 0) {
      toast.error(`Please provide: ${missingFields.join(", ")}.`);
      return;
    }

    const providerConfig = formSchemas[providerType];
    if (providerConfig) {
      const missingConfigFields = providerConfig.fields
        .filter((f) => f.required && !connectionData[f.name])
        .map((f) => f.label);
      if (missingConfigFields.length > 0) {
        toast.error(`Please provide: ${missingConfigFields.join(", ")}.`);
        return;
      }
    }

    setIsSubmitting(true);
    try {
      const payload = {
        name,
        provider_type: providerType,
        capability,
        connection_data: connectionData,
        connection_status: hasChangedSinceTest ? undefined : (testStatus ?? undefined),
        is_active: isActive ? 1 : 0,
        is_default: 0,
      };

      if (mode === "create") {
        const created = await createAudioProvider(payload);
        toast.success("Audio provider created successfully.");
        queryClient.invalidateQueries({ queryKey: ["audioProviders"] });
        onProviderSaved(created);
      } else {
        if (!providerId) throw new Error("Missing provider ID");
        const updated = await updateAudioProvider(providerId, payload);
        toast.success("Audio provider updated successfully.");
        queryClient.invalidateQueries({ queryKey: ["audioProviders"] });
        if (onProviderUpdated) onProviderUpdated(updated);
      }

      onOpenChange(false);
      resetForm();
    } catch {
      toast.error(`Failed to ${mode === "create" ? "create" : "update"} audio provider.`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const hasChangedSinceTest =
    testStatus !== null &&
    testedConnectionData !== null &&
    JSON.stringify(connectionData) !== JSON.stringify(testedConnectionData);

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px] p-0 overflow-hidden">
        <form onSubmit={handleSubmit} className="max-h-[90vh] overflow-y-auto overflow-x-hidden flex flex-col">
          <DialogHeader className="p-6 pb-4">
            <DialogTitle>
              {mode === "create" ? "Create Audio Provider" : "Edit Audio Provider"}
            </DialogTitle>
          </DialogHeader>
          <div className="px-6 pb-6 space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Provider name" />
            </div>

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
                        {config.display_name || config.name || type}
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
                  <Switch id="is_active" checked={isActive} onCheckedChange={setIsActive} />
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

          <DialogFooter className="px-6 py-4 border-t">
            <div className="flex justify-end gap-3 w-full">
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
                Cancel
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                {mode === "create" ? "Create" : "Update"}
              </Button>
            </div>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
