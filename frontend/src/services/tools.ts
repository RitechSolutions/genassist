
import { apiRequest } from "@/config/api";
import { Tool } from "@/interfaces/tool.interface";

const BASE = "genagent/tools";

export const getAllTools = () =>
  apiRequest<Tool[]>("GET", `${BASE}/`);

export const getToolById = (id: string) =>
  apiRequest<Tool>("GET", `${BASE}/${id}`);

export const createTool = (tool: Partial<Tool>) => {
  const toolWithId = {
    ...tool
  };
  
  return apiRequest<Tool>(
    "POST",
    `${BASE}/`,
    toolWithId as unknown as Record<string, unknown>
  );
};

export const updateTool = (id: string, tool: Partial<Tool>) =>
  apiRequest<Tool>("PUT", `${BASE}/${id}`, tool);

export const deleteTool = (id: string) =>
  apiRequest<void>("DELETE", `${BASE}/${id}`);

export const testPythonCode = (code: string, params: any) =>
  apiRequest<{ result: any }>(
    "POST",
    `${BASE}/python/test`,
    { code, params }
  );

export const testPythonCodeWithSchema = (code: string, params: any, schema: any) =>
  apiRequest<{
    result: any;
    original_params: any;
    validated_params: any;
  }>(
    "POST",
    `${BASE}/python/test-with-schema`,
    { code, params, schema }
  );

export const generatePythonTemplate = (schema: any) =>
  apiRequest<{ template: string }>(
    "POST",
    `${BASE}/python/generate-template`,
    { schema }
  );