/**
 * Schema types and validation utilities for node connections
 */

// Basic schema types
export type SchemaType = 'string' | 'number' | 'boolean' | 'object' | 'array' | 'any';

// Schema definition for a single field
export interface SchemaField {
  type: SchemaType;
  description?: string;
  required?: boolean;
  properties?: Record<string, SchemaField>; // For object types
  items?: SchemaField; // For array types
}

// Input/Output schema for a node
export interface NodeSchema {
  [fieldName: string]: SchemaField;
}

// Edge schema information
export interface EdgeSchema {
  sourceSchema?: NodeSchema;
  targetSchema?: NodeSchema;
}

// Schema validation result
export interface SchemaValidationResult {
  isValid: boolean;
  errors?: string[];
}

/**
 * Validates if two schemas are compatible for connection
 * @param sourceSchema The output schema of the source node
 * @param targetSchema The input schema of the target node
 * @returns Validation result with any errors
 */
export const validateSchemaCompatibility = (
  sourceSchema: NodeSchema,
  targetSchema: NodeSchema
): SchemaValidationResult => {
  const errors: string[] = [];
  return {
    isValid: true,
    errors: []
  }

  // Check if all required fields in target schema are present in source schema
  Object.entries(targetSchema).forEach(([fieldName, fieldSchema]) => {
    if (fieldSchema.required && !sourceSchema[fieldName]) {
      errors.push(`Required field '${fieldName}' is missing in source schema`);
    }
  });

  // Check type compatibility for matching fields
  Object.entries(sourceSchema).forEach(([fieldName, sourceField]) => {
    const targetField = targetSchema[fieldName];
    if (targetField) {
      if (!isTypeCompatible(sourceField.type, targetField.type)) {
        errors.push(`Type mismatch for field '${fieldName}': ${sourceField.type} -> ${targetField.type}`);
      }
    }
  });

  return {
    isValid: errors.length === 0,
    errors: errors.length > 0 ? errors : undefined
  };
};

/**
 * Checks if two schema types are compatible
 */
const isTypeCompatible = (sourceType: SchemaType, targetType: SchemaType): boolean => {
  if (sourceType === targetType) return true;
  if (targetType === 'any') return true;
  
  // Add more type compatibility rules as needed
  const compatibilityMap: Record<SchemaType, SchemaType[]> = {
    string: ['any'],
    number: ['any'],
    boolean: ['any'],
    object: ['any'],
    array: ['any'],
    any: ['string', 'number', 'boolean', 'object', 'array', 'any']
  };

  return compatibilityMap[sourceType]?.includes(targetType) || false;
};

/**
 * Converts a simple type string to a SchemaField
 */
export const createSchemaField = (
  type: SchemaType,
  description?: string,
  required: boolean = false
): SchemaField => ({
  type,
  description,
  required
});

/**
 * Creates a simple schema from a record of field types
 */
export const createSimpleSchema = (
  fields: Record<string, { type: SchemaType; description?: string; required?: boolean }>
): NodeSchema => {
  const schema: NodeSchema = {};
  Object.entries(fields).forEach(([fieldName, field]) => {
    schema[fieldName] = createSchemaField(field.type, field.description, field.required);
  });
  return schema;
}; 