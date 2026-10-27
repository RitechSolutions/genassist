import { apiRequest, getApiUrl, API_PREPROCESSING_TIMEOUT_MS } from "@/config/api";
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
): Promise<{ file_path: string | null; original_filename: string; file_id?: string; file_url?: string }> => {
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
    file_id?: string;
    file_url?: string;
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
    // Distinct values of a categorical column (up to 100), for ordering an
    // ordinal encoding; categories_truncated is set when there are more.
    categories?: string[];
    categories_truncated?: boolean;
    min?: number | null;
    max?: number | null;
  }>;
  // Training-file previews (analyze-file) read at most a fixed number of
  // rows; these say how much of the file the stats cover.
  rows_analyzed?: number;
  rows_truncated?: boolean;
  // Excel workbooks: every sheet, and the one previewed.
  sheet_names?: string[];
  sheet_name?: string;
}

export interface AnalyzeTrainingFileRequest {
  file_id?: string;
  file_url?: string;
  file_name?: string;
  sheet_name?: string;
}

// Preview an uploaded training file of any supported type (CSV, Parquet,
// Excel, JSON). Prefer file_id: it works with every storage provider.
/** Effective Train Data Source limits (GET /ml-models/training-data/limits). */
export interface TrainingDataLimits {
  max_upload_bytes: number;
  max_upload_label: string;
  json_max_bytes: number;
  max_rows: number;
  supported_extensions: string[];
}

export const getTrainingDataLimits = async (): Promise<TrainingDataLimits | null> => {
  try {
    return (await apiRequest<TrainingDataLimits>("GET", `${BASE}/training-data/limits`)) ?? null;
  } catch {
    // The server still enforces the limit; the UI just can't show it in advance.
    return null;
  }
};

export const analyzeTrainingFile = async (
  request: AnalyzeTrainingFileRequest,
): Promise<CSVAnalysisResult> => {
  const response = await apiRequest<CSVAnalysisResult>(
    "POST",
    `${BASE}/analyze-file`,
    { ...request },
    { timeout: API_PREPROCESSING_TIMEOUT_MS },
  );
  if (!response) throw new Error("Failed to preview the file");
  return response;
};

export const analyzeCSV = async (
  fileUrl: string,
  pythonCode?: string,
  file?: { id?: string; name?: string },
): Promise<CSVAnalysisResult> => {
  try {
    const body: {
      file_url: string;
      file_id?: string;
      file_name?: string;
      python_code?: string;
    } = {
      file_url: fileUrl,
    };
    if (file?.id) body.file_id = file.id;
    if (file?.name) body.file_name = file.name;
    if (pythonCode) {
      body.python_code = pythonCode;
    }
    const response = await apiRequest<CSVAnalysisResult>(
      "POST",
      `${BASE}/analyze-csv`,
      body,
      { timeout: API_PREPROCESSING_TIMEOUT_MS },
    );
    if (!response) throw new Error("Failed to analyze CSV");
    return response;
  } catch (error) {
    console.error("Error analyzing CSV:", error);
    throw error;
  }
};

export type ProfileDataRequest =
  | {
      source_type: "csv";
      file_id?: string;
      file_url?: string;
      file_name?: string;
      sheet_name?: string;
    }
  | {
      source_type: "datasource";
      data_source_id: string;
      query: string;
    };

/** Profiles an uploaded CSV or SQL query result and downloads the HTML report. */
export const profileData = async (
  request: ProfileDataRequest,
  downloadFilename: string,
): Promise<void> => {
  const blob = await apiRequest<Blob>(
    "POST",
    `${BASE}/profile-data`,
    request,
    { timeout: API_PREPROCESSING_TIMEOUT_MS, responseType: "blob" },
  );
  if (!blob) throw new Error("Failed to generate data profile");

  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = downloadFilename;
  a.click();
  URL.revokeObjectURL(objectUrl);
};
