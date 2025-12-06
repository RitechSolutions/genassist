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
    result = result.replace(new RegExp(`@${key}\\b`, "g"), value);
    result = result.replace(new RegExp(`{{${key}}}`, "g"), value);
  });
  return result;
};
