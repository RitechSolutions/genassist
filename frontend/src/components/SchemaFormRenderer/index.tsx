import { FieldSchema, FieldValue } from '@/interfaces/dynamicFormSchemas.interface';
import { FormFieldRenderer } from '@/components/FormFieldRenderer';
import { isFieldVisible } from './schemaFormUtils';

interface SchemaFormRendererProps {
  schema: { fields: FieldSchema[] };
  connectionData: Record<string, FieldValue>;
  onChange: (fieldName: string, value: FieldValue) => void;
  showAdvanced: boolean;
  advancedOnly?: boolean;
}

export function SchemaFormRenderer({
  schema,
  connectionData,
  onChange,
  showAdvanced,
  advancedOnly = false,
}: SchemaFormRendererProps) {
  const regularFields = schema.fields.filter((f) => f.required && isFieldVisible(f, connectionData));
  const advancedFields = schema.fields.filter((f) => !f.required && isFieldVisible(f, connectionData));

  const fieldsToRender = advancedOnly ? advancedFields : [...regularFields, ...(showAdvanced ? advancedFields : [])];

  function getExtras(field: FieldSchema): Record<string, FieldValue> | undefined {
    if (field.type === 'files') {
      return { original_filename: connectionData[`${field.name}_original_filename`] ?? '' };
    }
    return undefined;
  }

  function fieldValue(field: FieldSchema): FieldValue {
    const raw = connectionData[field.name] as FieldValue | null;
    // null marks a number the user cleared on purpose: show it empty rather
    // than the default, which would not be what gets saved.
    if (raw === null && field.type === 'number') return '';
    return raw ?? (field.default as FieldValue);
  }

  return (
    <div className="space-y-4">
      {fieldsToRender.map((field) => (
        <FormFieldRenderer
          key={field.name}
          field={field}
          value={fieldValue(field)}
          onChange={onChange}
          extras={getExtras(field)}
        />
      ))}
    </div>
  );
}
