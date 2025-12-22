import { FieldSchema } from "@/interfaces/dynamicFormSchemas.interface";

function isEmptyValue(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (typeof value === "string" && value.trim() === "") return true;
  if (Array.isArray(value) && value.length === 0) return true;
  return false;
}

export function getEmptyRequiredFields(
  data: Record<string, any>,
  schemas: FieldSchema[]
): string[] {
  if (!schemas || schemas.length === 0) return [];

  const missingFields: string[] = [];

  for (const field of schemas) {
    if (field.required) {
      const value = data[field.name];
      if (isEmptyValue(value)) {
        missingFields.push(field.label);
      }
    }
  }

  return missingFields;
}
