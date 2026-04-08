import React from "react";
import { FormFieldRenderer } from '@/components/FormFieldRenderer';
import { FieldSchema, FieldValue } from '@/interfaces/dynamicFormSchemas.interface';

interface DynamicRagFieldProps {
  field: FieldSchema;
  value: unknown;
  onChange: (name: string, value: unknown) => void;
  disabled?: boolean;
}

export const DynamicRagField: React.FC<DynamicRagFieldProps> = ({ field, value, onChange, disabled = false }) => (
  <FormFieldRenderer
    field={field}
    value={value as FieldValue}
    onChange={(name, val) => onChange(name, val)}
    disabled={disabled}
  />
);
