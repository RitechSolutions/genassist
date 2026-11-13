import { isCancel } from "axios";
import {
  api,
  apiRequest,
  formatUploadOrNetworkError,
  getApiUrl,
  API_PREPROCESSING_TIMEOUT_MS,
  API_UPLOAD_TIMEOUT_MS,
} from "@/config/api";
import { extractErrorMessage } from "@/helpers/apiError";
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

/**
 * Remove a .pkl uploaded for a save that was then rejected, so it doesn't stay in
 * File Manager. Best effort: a failure here must not hide the save error.
 */
export const discardModelUpload = (fileId: string): Promise<void> =>
  discardUnusedUpload(`${BASE}/upload`, fileId, "model file");

/**
 * Remove a Train Data Source upload the dialog no longer uses (rejected, replaced,
 * removed or cancelled). The server keeps any file a workflow or model still uses.
 * Best effort: a failure here is only logged.
 */
export const discardTrainingUpload = (fileId: string): Promise<void> =>
  discardUnusedUpload(`${BASE}/training-data/upload`, fileId, "training file");

/** Best-effort DELETE of an unused upload; a failure is only logged. */
const discardUnusedUpload = async (path: string, fileId: string, label: string): Promise<void> => {
  try {
    await apiRequest("DELETE", `${path}/${encodeURIComponent(fileId)}`);
  } catch (error) {
    console.warn(`Could not remove the unused ${label} upload:`, error);
  }
};

export interface ModelFileUpload {
  file_path: string | null;
  original_filename: string;
  file_id?: string;
  file_url?: string;
}

/**
 * Upload a .pkl for a model and report progress from 0 to 100.
 *
 * Uses the shared API client, so the login is renewed before the upload is sent and
 * once more if the server refuses an expired token (a long upload can outlive it).
 * Not through apiRequest: a proxy timeout on this one long request must not mark the
 * whole server as down. A failure is rethrown with a plain message (never a proxy's
 * HTML error page); a cancelled request, such as an ended session, is rethrown as is.
 */
export const uploadModelFile = async (
  file: File,
  onProgress?: (percent: number) => void,
): Promise<ModelFileUpload> => {
  const formData = new FormData();
  formData.append("file", file);
  try {
    const { data } = await api.post<ModelFileUpload>(`${await getApiUrl()}${BASE}/upload`, formData, {
      timeout: API_UPLOAD_TIMEOUT_MS,
      onUploadProgress: (event) => {
        if (!onProgress) return;
        const total = event.total || file.size;
        if (total > 0) onProgress(Math.min(100, Math.round((event.loaded * 100) / total)));
      },
    });
    if (!data) throw new Error("The model file could not be uploaded.");
    return data;
  } catch (error) {
    if (isCancel(error)) throw error;
    const status = (error as { response?: { status?: number } }).response?.status;
    if (status === 502 || status === 503 || status === 504) {
      throw new Error(
        "The server took too long to accept the model file. Try again; if it keeps happening, ask an admin to check the upload time limit.",
      );
    }
    throw new Error(formatUploadOrNetworkError(error));
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
  try {
    const response = await apiRequest<CSVAnalysisResult>(
      "POST",
      `${BASE}/analyze-file`,
      { ...request },
      { timeout: API_PREPROCESSING_TIMEOUT_MS },
    );
    if (!response) throw new Error("Failed to preview the file");
    return response;
  } catch (error) {
    // The server explains what is wrong with the file (e.g. two columns
    // with the same name); show that instead of the HTTP status.
    throw await actionableApiError(
      error,
      "The file preview could not be generated. Please try again.",
    );
  }
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
    throw await actionableApiError(
      error,
      "The file preview could not be generated. Please try again.",
    );
  }
};

export type QueryPreviewRequest = {
  data_source_id: string;
  query: string;
};

type ApiResponseError = {
  message?: unknown;
  response?: {
    data?: unknown;
  };
};

function actionableMessage(error: unknown, fallback: string): string {
  const message = extractErrorMessage(error, fallback);
  return /^Request failed with status code \d+$/i.test(message)
    ? fallback
    : message;
}

async function actionableApiError(
  error: unknown,
  fallback: string,
): Promise<Error> {
  const responseError = error as ApiResponseError;
  const responseData = responseError.response?.data;

  if (typeof Blob !== "undefined" && responseData instanceof Blob) {
    try {
      const text = await responseData.text();
      const parsed = JSON.parse(text) as unknown;
      return new Error(
        actionableMessage(
          {
            ...responseError,
            response: { ...responseError.response, data: parsed },
          },
          fallback,
        ),
      );
    } catch {
      return new Error(fallback);
    }
  }

  return new Error(actionableMessage(error, fallback));
}

/** Returns a bounded preview for a read-only database query. */
export const previewQuery = async (
  request: QueryPreviewRequest,
): Promise<CSVAnalysisResult> => {
  try {
    const response = await apiRequest<CSVAnalysisResult>(
      "POST",
      `${BASE}/preview-query`,
      request,
      { timeout: API_PREPROCESSING_TIMEOUT_MS },
    );
    if (!response) throw new Error("Failed to preview query");
    return response;
  } catch (error) {
    throw await actionableApiError(
      error,
      "The query preview could not be generated. Please try again.",
    );
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
  let blob: Blob | null;
  try {
    blob = await apiRequest<Blob>(
      "POST",
      `${BASE}/profile-data`,
      request,
      { timeout: API_PREPROCESSING_TIMEOUT_MS, responseType: "blob" },
    );
    if (!blob) throw new Error("Failed to generate data profile");
  } catch (error) {
    throw await actionableApiError(
      error,
      "The data profile could not be generated. Please try again.",
    );
  }

  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = downloadFilename;
  a.click();
  URL.revokeObjectURL(objectUrl);
};
