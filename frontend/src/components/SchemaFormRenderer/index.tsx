import { FieldSchema, FieldValue } from '@/interfaces/dynamicFormSchemas.interface';
import { FormFieldRenderer } from '@/components/FormFieldRenderer';

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
  const isFieldVisible = (field: FieldSchema): boolean => {
    if (!field.conditional) return true;
    return connectionData[field.conditional.field] === field.conditional.value;
  };

  const regularFields = schema.fields.filter((f) => f.required && isFieldVisible(f));
  const advancedFields = schema.fields.filter((f) => !f.required && isFieldVisible(f));

  const fieldsToRender = advancedOnly ? advancedFields : [...regularFields, ...(showAdvanced ? advancedFields : [])];

  function getExtras(field: FieldSchema): Record<string, FieldValue> | undefined {
    if (field.type === 'files') {
      return { original_filename: connectionData[`${field.name}_original_filename`] ?? '' };
    }
    return undefined;
  }

  return (
    <div className="space-y-4">
      {fieldsToRender.map((field) => (
        <FormFieldRenderer
          key={field.name}
          field={field}
          value={connectionData[field.name] ?? (field.default as FieldValue)}
          onChange={onChange}
          extras={getExtras(field)}
        />
      ))}
    </div>
  );
}
