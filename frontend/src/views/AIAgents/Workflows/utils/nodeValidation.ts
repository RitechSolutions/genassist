import { FieldSchema } from "@/interfaces/dynamicFormSchemas.interface";

function isEmptyValue(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (typeof value === "string" && value.trim() === "") return true;
  if (Array.isArray(value) && value.length === 0) return true;
  return false;
}

function shouldShowConditionalField(
  field: FieldSchema,
  data: object,
): boolean {
  if (!field.conditional) return true;

  const values = data as Record<string, unknown>;
  const conditionalFieldValue = values[field.conditional.field];
  const target = field.conditional.value;

  if (typeof target === "boolean") {
    const on =
      conditionalFieldValue === true ||
      conditionalFieldValue === "true" ||
      conditionalFieldValue === 1 ||
      conditionalFieldValue === "1";
    return target ? on : !on;
  }

  return conditionalFieldValue === target;
}

export function getEmptyRequiredFields(
  data: object,
  schemas: FieldSchema[],
): string[] {
  if (!schemas || schemas.length === 0) return [];

  const missingFields: string[] = [];
  const values = data as Record<string, unknown>;

  for (const field of schemas) {
    // Only validate required fields that should be shown based on conditionals
    if (field.required && shouldShowConditionalField(field, data)) {
      const names = [field.name, ...(field.alternative_names ?? [])];
      const hasValue = names.some((name) => !isEmptyValue(values[name]));
      if (!hasValue) {
        missingFields.push(field.label);
      }
    }
  }

  return missingFields;
}
