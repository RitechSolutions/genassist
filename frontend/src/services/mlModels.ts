import { apiRequest, getApiUrl } from "@/config/api";
import { MLModel, MLModelFormData } from "@/interfaces/ml-model.interface";

const BASE = "ml-models";

export const getAllMLModels = async (): Promise<MLModel[]> => { 
  return await apiRequest<MLModel[]>("GET", `${BASE}`) ?? [];
};

export const getMLModel = async (id: string): Promise<MLModel | null> => {
   return await apiRequest<MLModel>("GET", `${BASE}/${id}`) ?? null;
};

export const createMLModel = async (
  modelData: MLModelFormData,
): Promise<MLModel> => {
  try {
    return await apiRequest<MLModel>(
      "POST",
      `${BASE}`,
      modelData as unknown as Record<string, unknown>,
    ).catch((error) => {
      console.error("Error creating ML model:", error);
        throw error;
      });
  } catch (error) {
    console.error("Error creating ML model:", error);
    throw error;
  }
};

export const updateMLModel = async (
  id: string,
  modelData: Partial<MLModelFormData>,
): Promise<MLModel> => {
  try {
    return await apiRequest<MLModel>(
      "PUT",
      `${BASE}/${id}`,
      modelData as unknown as Record<string, unknown>,
    ).catch((error) => {
      console.error("Error updating ML model:", error);
      throw error;
    });
  } catch (error) {
    console.error("Error updating ML model:", error);
    throw error;
  }
};

export const deleteMLModel = async (id: string): Promise<void> => {
  try {
    return await apiRequest("DELETE", `${BASE}/${id}`);
  } catch (error) {
    console.error("Error deleting ML model:", error);
    throw error;
  }
};

export const uploadModelFile = async (
  file: File,
): Promise<{ file_path: string; original_filename: string }> => {
  try {
  const formData = new FormData();
  formData.append("file", file);

  const baseURL = await getApiUrl();
  const token = localStorage.getItem("access_token");
  const tokenType = localStorage.getItem("token_type");
  const tenantId = localStorage.getItem("tenant_id");

  const headers: Record<string, string> = {};

  if (token && tokenType) {
    headers["Authorization"] = `${tokenType} ${token}`;
  }

  if (tenantId) {
    headers["x-tenant-id"] = tenantId;
  }

  const response = await fetch(`${baseURL}${BASE}/upload`, {
    method: "POST",
    body: formData,
    headers,
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `API error: ${response.status}`);
  }

  return await response.json() as Promise<{
    file_path: string;
    original_filename: string;
  }>;
  } catch (error) {
    console.error("Error uploading model file:", error);
    throw error;
  }
};

export interface CSVAnalysisResult {
  row_count: number;
  column_count: number;
  column_names: string[];
  sample_data: Record<string, unknown>[];
  columns_info: Array<{
    name: string;
    dtype: string;
    missing_count: number;
    type: "categorical" | "numeric";
    unique_count: number;
    category_count?: number;
    min?: number | null;
    max?: number | null;
  }>;
}

export const analyzeCSV = async (
  fileUrl: string,
  pythonCode?: string,
): Promise<CSVAnalysisResult> => {
  try {
    const body: { file_url: string; python_code?: string } = {
      file_url: fileUrl,
    };
    if (pythonCode) {
      body.python_code = pythonCode;
    }
    const response = await apiRequest<CSVAnalysisResult>(
      "POST",
      `${BASE}/analyze-csv`,
      body,
    );
    if (!response) throw new Error("Failed to analyze CSV");
    return response;
  } catch (error) {
    console.error("Error analyzing CSV:", error);
    throw error;
  }
};
