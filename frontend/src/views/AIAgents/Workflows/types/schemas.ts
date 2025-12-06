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
  defaultValue?: string;
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

/**
 * Generates sample output data for a given schema
 * Uses default values when available, otherwise generates appropriate sample data
 * @param schema The schema to generate sample data for
 * @returns Sample data object matching the schema structure
 */
export const generateSampleOutput = (schema: NodeSchema): Record<string, unknown> => {
  const sampleData: Record<string, unknown> = {};
  if (!schema) return null;

  Object.entries(schema).forEach(([fieldName, fieldSchema]) => {
    if (fieldSchema.defaultValue !== undefined) {
      // Use the default value if provided
      sampleData[fieldName] = parseDefaultValue(fieldSchema.defaultValue, fieldSchema.type);
    } else {
      // Generate appropriate sample data based on type
      sampleData[fieldName] = generateSampleValue(fieldSchema);
    }
  });

  return sampleData;
};

/**
 * Parses a default value string to the appropriate type
 * @param defaultValue The default value as a string
 * @param type The expected schema type
 * @returns Parsed value of the correct type
 */
const parseDefaultValue = (defaultValue: string, type: SchemaType): unknown => {
  try {
    switch (type) {
      case 'string':
        return defaultValue;
      case 'number': {
        const num = parseFloat(defaultValue);
        return isNaN(num) ? defaultValue : num;
      }
      case 'boolean':
        if (defaultValue.toLowerCase() === 'true') return true;
        if (defaultValue.toLowerCase() === 'false') return false;
        return defaultValue; // Return as string if not parseable
      case 'object':
        try {
          return JSON.parse(defaultValue);
        } catch {
          return defaultValue; // Return as string if not parseable JSON
        }
      case 'array':
        try {
          return JSON.parse(defaultValue);
        } catch {
          return [defaultValue]; // Return as array with single item if not parseable
        }
      default:
        return defaultValue;
    }
  } catch {
    return defaultValue; // Fallback to string if parsing fails
  }
};

/**
 * Generates sample values for different schema types
 * @param fieldSchema The field schema to generate a sample for
 * @returns Generated sample value
 */
const generateSampleValue = (fieldSchema: SchemaField): unknown => {
  switch (fieldSchema.type) {
    case 'string':
      if (fieldSchema.description) {
        // Try to generate meaningful sample based on description
        const desc = fieldSchema.description.toLowerCase();
        if (desc.includes('email')) return 'user@example.com';
        if (desc.includes('name')) return 'Sample Name';
        if (desc.includes('id')) return 'sample-id-123';
        if (desc.includes('url')) return 'https://example.com';
        if (desc.includes('phone')) return '+1-555-123-4567';
        if (desc.includes('date')) return '2024-01-15';
        if (desc.includes('time')) return '14:30:00';
      }
      return 'sample_string';
    
    case 'number':
      if (fieldSchema.description) {
        const desc = fieldSchema.description.toLowerCase();
        if (desc.includes('count') || desc.includes('total')) return 42;
        if (desc.includes('price') || desc.includes('cost')) return 99.99;
        if (desc.includes('percentage')) return 75.5;
        if (desc.includes('age')) return 30;
        if (desc.includes('year')) return 2024;
      }
      return 123;
    
    case 'boolean':
      return true;
    
    case 'object':
      if (fieldSchema.properties) {
        return generateSampleOutput(fieldSchema.properties);
      }
      return { key: 'value' };
    
    case 'array':
      if (fieldSchema.items) {
        // Generate array with 2-3 sample items
        const itemCount = Math.floor(Math.random() * 2) + 2;
        const items = [];
        for (let i = 0; i < itemCount; i++) {
          items.push(generateSampleValue(fieldSchema.items));
        }
        return items;
      }
      return ['item1', 'item2', 'item3'];
    
    case 'any':
      return 'sample_value';
    
    default:
      return 'unknown_type_sample';
  }
};

/**
 * Generates sample output for a specific field
 * @param fieldName The name of the field
 * @param fieldSchema The field schema
 * @returns Sample value for the specific field
 */
export const generateFieldSample = (fieldName: string, fieldSchema: SchemaField): unknown => {
  if (fieldSchema.defaultValue !== undefined) {
    return parseDefaultValue(fieldSchema.defaultValue, fieldSchema.type);
  }
  return generateSampleValue(fieldSchema);
}; 