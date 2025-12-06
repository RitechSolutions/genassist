/**
 * Unified schema definitions for dynamic field schemas.
 * 
 * This module provides a unified structure for all dynamic field schemas
 * to ensure consistency and maintainability.
 */

// Field types supported across all schemas
export type FieldType = "text" | "number" | "password" | "select" | "boolean" | "tags";

/**
 * Conditional field definition for showing/hiding fields based on other field values.
 */
export interface ConditionalField {
  field: string; // Field name to check
  value: string | number | boolean; // Value to match
}

/**
 * Unified field schema definition for all dynamic schemas.
 */
export interface FieldSchema {
  name: string; // Field name/identifier
  type: FieldType; // Field type
  label: string; // Display label for the field
  required: boolean; // Whether field is required (default: false)
  description?: string; // Field description
  placeholder?: string; // Placeholder text
  default?: string | number | boolean; // Default value

  // For select fields
  options?: Array<{ value: string; label: string }>; // Options for select fields

  // For number fields
  min?: number; // Minimum value for number fields
  max?: number; // Maximum value for number fields
  step?: number; // Step value for number fields

  // For conditional fields (DATA_SOURCE style)
  conditional?: ConditionalField; // Conditional field logic

  // For encryption (APP_SETTINGS style)
  encrypted?: boolean; // Whether field should be encrypted (default: false)

  // For advanced fields (DATA_SOURCE style)
  advanced?: boolean; // Whether field is advanced/optional to show

  // Allow extra fields for backwards compatibility
  [key: string]: unknown;
}

/**
 * Section schema for grouping fields.
 */
export interface SectionSchema {
  name: string; // Section name/identifier
  label: string; // Display label for the section
  fields: FieldSchema[]; // Fields in this section
  conditional_fields?: {
    [conditionValue: string]: FieldSchema[];
  }; // Conditional fields based on field values (e.g., {'recursive': [FieldSchema, ...]})

  // Allow extra fields for backwards compatibility
  [key: string]: unknown;
}

/**
 * Unified type schema definition for all dynamic schemas.
 * 
 * Supports two patterns:
 * 1. Flat structure: Direct 'fields' array (DATA_SOURCE, APP_SETTINGS, LLM_FORM)
 * 2. Sectioned structure: 'sections' array (AGENT_RAG_FORM)
 */
export interface TypeSchema {
  name: string; // Type name
  description?: string; // Type description

  // For flat structure (DATA_SOURCE, APP_SETTINGS, LLM_FORM)
  fields?: FieldSchema[]; // Direct fields array

  // For sectioned structure (AGENT_RAG_FORM)
  sections?: SectionSchema[]; // Sections with fields

  // Allow extra fields for backwards compatibility
  [key: string]: unknown;
}

/**
 * Dynamic form schema for all dynamic form schemas.
 * This is the top-level type returned by all form_schemas endpoints.
 */
export interface DynamicFormSchema {
  [key: string]: TypeSchema;
}

