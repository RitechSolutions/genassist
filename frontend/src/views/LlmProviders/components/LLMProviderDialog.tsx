import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { SimpleInput as Input } from "@/components/ui/simpleInput";
import { Label } from '@/components/label';
import { Switch } from "@/components/switch";
import { Button } from "@/components/button";
import { Loader2 } from "lucide-react";
import { toast } from "react-hot-toast";
import {
  createLLMProvider,
  getLLMProvidersFormSchemas,
  testLLMProviderConnection,
  updateLLMProvider,
} from '@/services/llmProviders';
import { LLMProvider } from "@/interfaces/llmProvider.interface";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/select";
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ConnectionTestPanel } from '@/components/ConnectionTestPanel';
import type { ConnectionStatus } from '@/interfaces/connectionStatus.interface';
import { SchemaFormRenderer } from '@/components/SchemaFormRenderer';
import type { FieldSchema, FieldValue } from '@/interfaces/dynamicFormSchemas.interface';

function hasAdvancedFieldChanges(fields: FieldSchema[], data: Record<string, FieldValue>): boolean {
  return fields
    .filter((f) => !f.required)
    .some((f) => {
      const val = data[f.name];
      if (val === undefined || val === null || val === '') return false;
      if (Array.isArray(val) && val.length === 0) return false;
      return val !== (f.default ?? null);
    });
}

interface LLMProviderDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onProviderSaved: (provider?: LLMProvider) => void;
  onProviderUpdated?: (provider: LLMProvider) => void;
  providerToEdit?: LLMProvider | null;
  mode?: "create" | "edit";
}

export function LLMProviderDialog({
  isOpen,
  onOpenChange,
  onProviderSaved,
  onProviderUpdated,
  providerToEdit = null,
  mode = "create",
}: LLMProviderDialogProps) {
  const [providerId, setProviderId] = useState<string>(providerToEdit?.id);
  const [name, setName] = useState(providerToEdit?.name ?? '');
  const [llmType, setLlmType] = useState<string>(providerToEdit?.llm_model_provider ?? '');
  const [llmModel, setLlmModel] = useState<string>(providerToEdit?.llm_model ?? '');

  const [isActive, setIsActive] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [connectionData, setConnectionData] = useState<Record<string, string | number | string[]>>(
    providerToEdit?.connection_data ?? {}
  );

  const [showAdvanced, setShowAdvanced] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testStatus, setTestStatus] = useState<ConnectionStatus | null>(null);
  const [testedConnectionData, setTestedConnectionData] = useState<Record<string, string | number | string[]> | null>(
    null
  );
  const queryClient = useQueryClient();

  const { data, isLoading: isLoadingConfig } = useQuery({
    queryKey: ['supportedModels'],
    queryFn: () => getLLMProvidersFormSchemas(),
    refetchOnWindowFocus: false,
  });

  const supportedModels = data ?? {};

  useEffect(() => {
    if (isOpen) {
      if (providerToEdit) {
        setProviderId(providerToEdit.id);
        setName(providerToEdit.name);
        setLlmType(providerToEdit.llm_model_provider);
        setLlmModel(providerToEdit.llm_model);
        setConnectionData(providerToEdit.connection_data);
        setIsActive(providerToEdit.is_active === 1);
        setShowAdvanced(
          hasAdvancedFieldChanges(
            supportedModels[providerToEdit.llm_model_provider]?.fields ?? [],
            providerToEdit.connection_data
          )
        );
        setTestStatus(providerToEdit.connection_status ?? null);
        setTestedConnectionData(
          providerToEdit.connection_status ? structuredClone(providerToEdit.connection_data) : null
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
    setName('');
    setLlmType('');
    setConnectionData({});
    setIsActive(true);
    setShowAdvanced(false);
    setTestStatus(null);
    setTestedConnectionData(null);
  };

  const handleConnectionDataChange = (fieldName: string, value: string | number | string[]) => {
    if (fieldName === 'model') {
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
        const result = await testLLMProviderConnection(llmType, connectionData, providerId);
        setTestStatus({
          status: result.success ? 'Connected' : 'Error',
          last_tested_at: new Date().toISOString(),
          message: result.message,
        });
        setTestedConnectionData(structuredClone(connectionData));
      } catch {
        setTestStatus({
          status: 'Error',
          last_tested_at: new Date().toISOString(),
          message: 'Test failed.',
        });
        setTestedConnectionData(structuredClone(connectionData));
      } finally {
        setIsTesting(false);
      }
    };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const requiredFields = [
      { label: 'Name', isEmpty: !name },
      { label: 'Type', isEmpty: !llmType },
    ];

    const missingBasicFields = requiredFields.filter((field) => field.isEmpty).map((field) => field.label);

    if (missingBasicFields.length > 0) {
      if (missingBasicFields.length === 1) {
        toast.error(`${missingBasicFields[0]} is required.`);
      } else {
        toast.error(`Please provide: ${missingBasicFields.join(', ')}.`);
      }
      return;
    }

    const providerConfig = supportedModels[llmType];
    if (!providerConfig) {
      toast.error('Invalid provider type.');
      return;
    }

    // Validate provider-specific required fields
    const missingFields = providerConfig.fields
      .filter((field) => field.required && !connectionData[field.name])
      .map((field) => field.label);

    if (missingFields.length > 0) {
      if (missingFields.length === 1) {
        toast.error(`${missingFields[0]} is required.`);
      } else {
        toast.error(`Please provide: ${missingFields.join(', ')}.`);
      }
      return;
    }

    setIsSubmitting(true);
    try {
      const data = {
        name,
        llm_model_provider: llmType,
        llm_model: llmModel,
        connection_data: connectionData,
        connection_status: hasChangedSinceTest ? undefined : (testStatus ?? undefined),
        is_active: isActive ? 1 : 0,
      };

      if (mode === 'create') {
        const created = await createLLMProvider(data);
        toast.success('LLM provider created successfully.');
        queryClient.invalidateQueries({ queryKey: ['llmProviders'] });
        onProviderSaved(created);
      } else {
        if (!providerId) throw new Error('Missing provider ID');
        const updated = await updateLLMProvider(providerId, data);
        toast.success('LLM provider updated successfully.');
        queryClient.invalidateQueries({ queryKey: ['llmProviders'] });
        if (onProviderUpdated) {
          onProviderUpdated(updated);
        }
      }

      onOpenChange(false);
      resetForm();
    } catch (error) {
      toast.error(`Failed to ${mode === 'create' ? 'create' : 'update'} LLM provider.`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const hasOptionalFields = (supportedModels[llmType]?.fields.filter((f) => !f.required) ?? []).length > 0;

  const hasAdvancedChanges = hasAdvancedFieldChanges(supportedModels[llmType]?.fields ?? [], connectionData);

  useEffect(() => {
    if (hasAdvancedChanges) setShowAdvanced(true);
  }, [hasAdvancedChanges]);

  const hasChangedSinceTest =
    testStatus !== null &&
    testedConnectionData !== null &&
    JSON.stringify(connectionData) !== JSON.stringify(testedConnectionData);
  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px] p-0 overflow-hidden">
        <form onSubmit={handleSubmit} className="max-h-[90vh] overflow-y-auto overflow-x-hidden flex flex-col">
          <DialogHeader className="p-6 pb-4">
            <DialogTitle>{mode === 'create' ? 'Create LLM Provider' : 'Edit LLM Provider'}</DialogTitle>
          </DialogHeader>
          <div className="px-6 pb-6 space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Provider name" />
            </div>

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
                    {Object.entries(supportedModels).map(([type, providerConfig]) => (
                      <SelectItem key={type} value={type}>
                        {providerConfig.name}
                      </SelectItem>
                    ))}
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
                  <div className="flex items-center gap-2">
                    <Label htmlFor="is_active">Active</Label>
                    <Switch id="is_active" checked={isActive} onCheckedChange={setIsActive} />
                  </div>
                  <div className="flex-1" />
                  {hasOptionalFields && (
                    <div className="flex items-center gap-2">
                      <Label htmlFor="show_advanced">Advanced</Label>
                      <Switch id="show_advanced" checked={showAdvanced} onCheckedChange={setShowAdvanced} />
                    </div>
                  )}
                </div>
                {showAdvanced && (
                  <SchemaFormRenderer
                    schema={{ fields: supportedModels[llmType].fields }}
                    connectionData={connectionData}
                    onChange={handleConnectionDataChange}
                    showAdvanced={true}
                    advancedOnly={true}
                  />
                )}
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
                {mode === 'create' ? 'Create' : 'Update'}
              </Button>
            </div>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
