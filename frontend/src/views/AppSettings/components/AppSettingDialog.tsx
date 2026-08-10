import { useState, useEffect } from 'react';
import { Button } from '@/components/button';
import { Input } from '@/components/ui/input';
import {
  createAppSetting,
  getAppSettingsFormSchemas,
  testAppSettingConnection,
  updateAppSetting,
} from '@/services/appSettings';
import { Switch } from '@/components/switch';
import { Label } from '@/components/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/select';
import { toast } from 'react-hot-toast';
import { Loader2, Plus, X } from 'lucide-react';
import { AppSetting } from '@/interfaces/app-setting.interface';
import { useQuery } from '@tanstack/react-query';
import { SchemaFormRenderer } from '@/components/SchemaFormRenderer';
import { getSchemaDefaults, isFieldVisible } from '@/components/SchemaFormRenderer/schemaFormUtils';
import { ConnectionTestPanel } from '@/components/ConnectionTestPanel';
import { CollapsibleSection } from '@/components/CollapsibleSection';
import { CRUDDialog } from '@/components/ui/crud-dialog';
import { CredentialSetupGuidePanel } from './CredentialSetupGuidePanel';
import { CREDENTIAL_SETUP_GUIDES } from './credentialSetupGuides';
import type { ConnectionStatus } from '@/interfaces/connectionStatus.interface';
import type { FieldSchema, FieldValue } from '@/interfaces/dynamicFormSchemas.interface';

interface AppSettingDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onSettingSaved: (createdOrUpdated?: AppSetting) => void;
  settingToEdit?: AppSetting | null;
  mode?: 'create' | 'edit';
  initialType?: AppSetting['type'];
  // When true, the Type select is disabled
  disableTypeSelect?: boolean;
}

export function AppSettingDialog({
  isOpen,
  onOpenChange,
  onSettingSaved,
  settingToEdit = null,
  mode = 'create',
  initialType,
  disableTypeSelect = false,
}: AppSettingDialogProps) {
  const [name, setName] = useState('');
  const [type, setType] = useState<AppSetting['type']>('Other');
  const [values, setValues] = useState<Record<string, FieldValue>>({});
  const [description, setDescription] = useState('');
  const [isActive, setIsActive] = useState(true);
  const [isTesting, setIsTesting] = useState(false);
  const [testStatus, setTestStatus] = useState<ConnectionStatus | null>(null);
  const [testedValues, setTestedValues] = useState<Record<string, FieldValue> | null>(null);
  const [customFields, setCustomFields] = useState<Array<{ key: string; value: string }>>([{ key: '', value: '' }]);

  // Types whose credentials support a connection test (backend dispatch in
  // AppSettingsService.test_connection).
  const TESTABLE_TYPES: Array<AppSetting['type']> = ['Salesforce', 'Zendesk'];
  const canTestConnection = TESTABLE_TYPES.includes(type);
  const setupGuide = CREDENTIAL_SETUP_GUIDES[type];
  const [showSetupGuide, setShowSetupGuide] = useState(false);
  const hasChangedSinceTest =
    testStatus !== null &&
    testedValues !== null &&
    JSON.stringify(values) !== JSON.stringify(testedValues);

  const { data, isLoading: isLoadingConfig } = useQuery({
    queryKey: ['appSettingSchemas'],
    queryFn: () => getAppSettingsFormSchemas(),
    refetchOnWindowFocus: false,
  });

  const appSettingSchemas = data ?? {};

  // Seed a type's schema-declared field defaults (e.g. Zendesk's auth_method) so that
  // conditional fields keyed off a defaulted select are visible immediately.
  const schemaDefaultsFor = (settingType: AppSetting['type']): Record<string, FieldValue> =>
    getSchemaDefaults(appSettingSchemas[settingType]?.fields ?? []);

  // Labels of required, currently-visible fields the user hasn't filled in — shared by
  // the submit and test-connection validators.
  const missingRequiredLabels = (schema: { fields?: FieldSchema[] }): string[] =>
    (schema.fields ?? [])
      .filter((field) => {
        if (!field.required || !isFieldVisible(field, values)) return false;
        const value = values[field.name];
        return value === undefined || value === '' || (Array.isArray(value) && value.length === 0);
      })
      .map((field) => field.label);

  useEffect(() => {
    if (isOpen) {
      resetForm();
      if (settingToEdit && mode === 'edit') {
        populateFormWithSetting(settingToEdit);
      } else if (mode === 'create' && initialType) {
        setType(initialType);
        // Seed defaults here (not only in the schema-load effect below) so a preset
        // type is populated on every open — including reopens where `type` is
        // unchanged and the type-keyed effect would not re-fire.
        setValues(schemaDefaultsFor(initialType));
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, settingToEdit, mode]);

  // In create mode, seed the selected type's defaults once its schema is available.
  // Covers the first open where the type is set before the schema query resolves.
  // Only seeds when the user hasn't entered values yet.
  useEffect(() => {
    if (mode !== 'create' || type === 'Other') return;
    if (!appSettingSchemas[type]?.fields) return;
    setValues((prev) => (Object.keys(prev).length === 0 ? schemaDefaultsFor(type) : prev));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [type, data, mode]);

  const resetForm = () => {
    setName('');
    setType('Other');
    setValues({});
    setDescription('');
    setIsActive(true);
    setCustomFields([{ key: '', value: '' }]);
    setTestStatus(null);
    setTestedValues(null);
  };

  const populateFormWithSetting = (setting: AppSetting) => {
    setName(setting.name);
    setType(setting.type);
    setValues(setting.values || {});
    setDescription(setting.description || '');
    setIsActive(setting.is_active === 1);

    // For "Other" type, populate custom fields
    if (setting.type === 'Other') {
      const fields = Object.entries(setting.values || {}).map(([key, value]) => ({
        key,
        value: value as string,
      }));
      setCustomFields(fields.length > 0 ? fields : [{ key: '', value: '' }]);
    } else {
      // For non-Other types, ensure custom fields are reset
      setCustomFields([{ key: '', value: '' }]);
    }
  };

  const handleValuesChange = (fieldName: string, value: FieldValue) => {
    setValues((prev) => ({
      ...prev,
      [fieldName]: value,
    }));
  };

  const handleCustomFieldChange = (index: number, field: 'key' | 'value', value: string) => {
    setCustomFields((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };
      return updated;
    });
  };

  const addCustomField = () => {
    setCustomFields((prev) => [...prev, { key: '', value: '' }]);
  };

  const removeCustomField = (index: number) => {
    setCustomFields((prev) => prev.filter((_, i) => i !== index));
  };

  // Build the values payload for the "Other" type from the custom key/value rows.
  const buildOtherValues = (): Record<string, FieldValue> => {
    const finalValues: Record<string, FieldValue> = {};
    customFields.forEach((field) => {
      if (field.key.trim()) {
        finalValues[field.key.trim()] = field.value || '';
      }
    });
    return finalValues;
  };

  const handleTestConnection = async () => {
    // Validate required schema fields before hitting the connector.
    const schema = appSettingSchemas[type];
    if (schema) {
      const schemaMissing = missingRequiredLabels(schema);
      if (schemaMissing.length > 0) {
        toast.error(`Please provide: ${schemaMissing.join(', ')}.`);
        return;
      }
    }

    setIsTesting(true);
    setTestStatus(null);
    try {
      const result = await testAppSettingConnection(type, values);
      setTestStatus({
        status: result.success ? 'Connected' : 'Error',
        last_tested_at: new Date().toISOString(),
        message: result.message,
      });
      setTestedValues(structuredClone(values));
    } catch {
      setTestStatus({
        status: 'Error',
        last_tested_at: new Date().toISOString(),
        message: 'Test failed.',
      });
      setTestedValues(structuredClone(values));
    } finally {
      setIsTesting(false);
    }
  };

  const hasOptionalFields =
    type !== 'Other' && appSettingSchemas[type] ? appSettingSchemas[type].fields.some((f) => !f.required) : false;

  return (
    <CRUDDialog<Record<string, unknown>>
      open={isOpen}
      onOpenChange={onOpenChange}
      mode={mode}
      maxWidth="500px"
      initialValues={{}}
      title={{ create: 'Create Configuration', edit: 'Edit Configuration' }}
      submitLabel={{ create: 'Create', edit: 'Update' }}
      loadingLabel={{ create: 'Create', edit: 'Update' }}
      successMessage={{
        create: 'App setting created successfully.',
        edit: 'App setting updated successfully.',
      }}
      errorMessage={(_err, m) => `Failed to ${m} app setting.`}
      validate={() => {
        const missingFields: string[] = [];
        if (!name) missingFields.push('Name');
        if (!type) missingFields.push('Type');
        if (missingFields.length > 0) {
          toast.error(
            missingFields.length === 1
              ? `${missingFields[0]} is required.`
              : `Please provide: ${missingFields.join(', ')}.`
          );
          return { _error: 'invalid' };
        }

        // Validate schema-based fields. Use the shared, visibility-aware helper so
        // conditionally-hidden required fields (e.g. Zendesk's OAuth creds under a
        // non-selected auth method) aren't flagged as missing for a field the user
        // can't see.
        if (type !== 'Other' && appSettingSchemas[type]) {
          const schema = appSettingSchemas[type];
          const schemaMissing = missingRequiredLabels(schema);

          if (schemaMissing.length > 0) {
            toast.error(
              schemaMissing.length === 1
                ? `${schemaMissing[0]} is required.`
                : `Please provide: ${schemaMissing.join(', ')}.`
            );
            return { _error: 'invalid' };
          }
        }

        // For "Other" type, require at least one custom field
        if (type === 'Other' && Object.keys(buildOtherValues()).length === 0) {
          toast.error('Please add at least one custom field.');
          return { _error: 'invalid' };
        }

        return null;
      }}
      onSubmit={async (_v, { mode: m }) => {
        const finalValues = type === 'Other' ? buildOtherValues() : values;
        const data: Partial<AppSetting> = {
          name,
          type,
          values: finalValues,
          description: description || undefined,
          is_active: isActive ? 1 : 0,
        };

        if (m === 'create') {
          const created = await createAppSetting(data);
          onSettingSaved(created);
        } else {
          if (!settingToEdit?.id) throw new Error('Missing app setting ID');
          const updated = await updateAppSetting(settingToEdit.id, data);
          onSettingSaved(updated);
        }
      }}
    >
      <div className="space-y-2">
        <Label htmlFor="name">Name</Label>
        <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" />
      </div>

      <div className="space-y-2">
        <Label htmlFor="type">Type</Label>
        {isLoadingConfig ? (
          <div className="flex items-center justify-center p-4">
            <Loader2 className="w-6 h-6 animate-spin" />
          </div>
        ) : (
          <Select
            value={type}
            onValueChange={(value) => {
              const newType = value as AppSetting['type'];
              setType(newType);

              // A prior test result / open guide belongs to the old type — clear
              // them so the panel and guide reflect the newly selected type.
              setTestStatus(null);
              setTestedValues(null);
              setShowSetupGuide(false);

              if (newType === 'Other') {
                setValues({});
                setCustomFields([{ key: '', value: '' }]);
              } else {
                if (type === 'Other' || mode === 'create') {
                        // Seed schema defaults so conditional fields (e.g. Zendesk's
                        // OAuth credentials under the default auth method) show at once.
                  setValues(schemaDefaultsFor(newType));
                }
                setCustomFields([{ key: '', value: '' }]);
              }
            }}
          >
            <SelectTrigger className="w-full" disabled={disableTypeSelect}>
              <SelectValue placeholder="Select Type" />
            </SelectTrigger>
            <SelectContent>
              {Object.keys(appSettingSchemas)
                .filter((key) => key !== 'FileManagerSettings' && key !== 'Security')
                .map((key) => (
                  <SelectItem key={key} value={key}>
                    {appSettingSchemas[key].name}
                  </SelectItem>
                ))}
              <SelectItem value="Other">Other</SelectItem>
            </SelectContent>
          </Select>
        )}
      </div>

      {setupGuide && (
        <CollapsibleSection
          title={setupGuide.title ?? 'How to get these values'}
          open={showSetupGuide}
          onOpenChange={() => setShowSetupGuide((prev) => !prev)}
        >
          <CredentialSetupGuidePanel guide={setupGuide} />
        </CollapsibleSection>
      )}

      {type && (
        <>
          {type === 'Other' ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <Label>Custom Fields</Label>
                <Button type="button" variant="outline" size="sm" onClick={addCustomField}>
                  <Plus className="w-4 h-4 mr-1" />
                  Add Field
                </Button>
              </div>
              {customFields.map((field, index) => (
                <div key={index} className="flex gap-2 items-end">
                  <div className="flex-1 space-y-2">
                    <Label htmlFor={`custom-key-${index}`}>Key</Label>
                    <Input
                      id={`custom-key-${index}`}
                      value={field.key}
                      onChange={(e) => handleCustomFieldChange(index, 'key', e.target.value)}
                      placeholder="Field key"
                    />
                  </div>
                  <div className="flex-1 space-y-2">
                    <Label htmlFor={`custom-value-${index}`}>Value</Label>
                    <Input
                      id={`custom-value-${index}`}
                      value={field.value}
                      onChange={(e) => handleCustomFieldChange(index, 'value', e.target.value)}
                      placeholder="Field value"
                      type="password"
                    />
                  </div>
                  {customFields.length > 1 && (
                    <Button type="button" variant="ghost" size="sm" onClick={() => removeCustomField(index)}>
                      <X className="w-4 h-4" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-4">
              <SchemaFormRenderer
                schema={{ fields: appSettingSchemas[type].fields }}
                connectionData={values}
                onChange={handleValuesChange}
                showAdvanced={false}
              />
              {hasOptionalFields && (
                <div className="pt-2 border-t">
                  <SchemaFormRenderer
                    schema={{ fields: appSettingSchemas[type].fields }}
                    connectionData={values}
                    onChange={handleValuesChange}
                    showAdvanced={true}
                    advancedOnly={true}
                  />
                </div>
              )}
              {canTestConnection && (
                <ConnectionTestPanel
                  isTesting={isTesting}
                  testStatus={testStatus}
                  hasChangedSinceTest={hasChangedSinceTest}
                  onTest={handleTestConnection}
                />
              )}
            </div>
          )}
        </>
      )}

      <div className="space-y-2">
        <Label htmlFor="description">Description (Optional)</Label>
        <Input
          id="description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Description"
        />
      </div>

      <div className="flex items-center gap-2 pt-2 border-t">
        <Label htmlFor="is_active">Active</Label>
        <Switch id="is_active" checked={isActive} onCheckedChange={setIsActive} />
      </div>
    </CRUDDialog>
  );
}
