import { FieldSchema } from "@/interfaces/dynamicFormSchemas.interface";

function isEmptyValue(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (typeof value === "string" && value.trim() === "") return true;
  if (Array.isArray(value) && value.length === 0) return true;
  return false;
}

function shouldShowConditionalField(
  field: FieldSchema,
  data: Record<string, any>,
): boolean {
  if (!field.conditional) return true;

  const conditionalFieldValue = data[field.conditional.field];
  return conditionalFieldValue === field.conditional.value;
}

export function getEmptyRequiredFields(
  data: Record<string, any>,
  schemas: FieldSchema[],
): string[] {
  if (!schemas || schemas.length === 0) return [];

  const missingFields: string[] = [];

  for (const field of schemas) {
    // Only validate required fields that should be shown based on conditionals
    if (field.required && shouldShowConditionalField(field, data)) {
      const value = data[field.name];
      if (isEmptyValue(value)) {
        missingFields.push(field.label);
      }
    }
  }

  return missingFields;
}
