/**
 * Helper functions for API-related operations
 */

/**
 * Extracts dynamic variables from a text string
 * @param text The text to extract variables from
 * @returns Set of variable names (without @ or {{}} prefix/suffix)
 */
export const extractDynamicVariables = (text: string): Set<string> => {
  const variables = new Set<string>();
  
  // Match @variable format
  const atMatches = text.match(/@\w+/g) || [];
  atMatches.forEach(v => variables.add(v.slice(1)));
  
  // Match {{variable}} format
  const curlyMatches = text.match(/{{([^}]+)}}/g) || [];
  curlyMatches.forEach(v => variables.add(v.slice(2, -2).trim()));
  
  return variables;
};

/**
 * Gets all dynamic variables from an API configuration
 * @param endpoint The API endpoint URL
 * @param parameters Record of parameter key-value pairs
 * @param requestBody The request body string
 * @returns Set of all unique variable names found in the configuration
 */
export const getAllDynamicVariables = (
  endpoint: string,
  headers: Record<string, string>,
  parameters: Record<string, string>,
  requestBody: string
): Set<string> => {
  const variables = new Set<string>();
  console.log(endpoint, parameters, requestBody);
  
  // Extract from URL
  extractDynamicVariables(endpoint).forEach(v => variables.add(v));
  
  // Extract from parameters
  Object.values(parameters).forEach(value => {
    extractDynamicVariables(value).forEach(v => variables.add(v));
  });
  Object.values(headers).forEach(value => {
    extractDynamicVariables(value).forEach(v => variables.add(v));
  });
  
  
  // Extract from request body
  if (requestBody) {
    extractDynamicVariables(requestBody).forEach(v => variables.add(v));
  }
  
  return variables;
};

/**
 * Replaces variables in text with their input values
 * @param text The text containing variables to replace
 * @param inputs Record of variable names and their values
 * @returns Text with all variables replaced with their values
 */
export const replaceVariablesWithInputs = (
  text: string,
  inputs: Record<string, string>
): string => {
  let result = text;
  Object.entries(inputs).forEach(([key, value]) => {
    // Replace both @variable and {{variable}} formats
    result = result.replace(new RegExp(`@${key}\\b`, 'g'), value);
    result = result.replace(new RegExp(`{{${key}}}`, 'g'), value);
  });
  return result;
}; 