import type { FieldSchema, FieldValue } from '@/interfaces/dynamicFormSchemas.interface';

/**
 * Shared helpers for schema-driven forms (used by SchemaFormRenderer and the
 * data-source / app-setting dialogs) so the conditional-visibility and default
 * rules live in one place.
 */

/**
 * A field is visible when it has no `conditional`, or when its controlling
 * field currently holds the matching value (e.g. an OAuth secret shown only
 * when the auth method is set to client credentials).
 */
export function isFieldVisible(field: Pick<FieldSchema, 'conditional'>, values: Record<string, FieldValue>): boolean {
  if (!field.conditional) return true;
  return values[field.conditional.field] === field.conditional.value;
}

/**
 * Collect the schema-declared default values for a set of fields, so a form can
 * seed them into its state (making conditional fields keyed off a defaulted
 * select visible immediately).
 */
export function getSchemaDefaults(fields: FieldSchema[]): Record<string, FieldValue> {
  const defaults: Record<string, FieldValue> = {};
  for (const field of fields) {
    if (field.default !== undefined && field.default !== null) {
      defaults[field.name] = field.default;
    }
  }
  return defaults;
}
