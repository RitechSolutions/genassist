import { apiRequest } from "@/config/api";
import {
  TrainingPipelineConfig,
  PipelineRun,
  PipelineArtifact,
  PipelineRunCreatePayload,
  TrainingPipelineConfigCreatePayload,
  TrainingPipelineConfigUpdatePayload,
} from "@/interfaces/ml-model-pipeline.interface";

const BASE = "ml-models";

// Training Pipeline Configuration
export const getModelPipelineConfigs = async (modelId: string): Promise<TrainingPipelineConfig[]> => {
  try {
    const data = await apiRequest<TrainingPipelineConfig[]>("GET", `${BASE}/${modelId}/pipeline-configs`);
    return data || [];
  } catch (error) {
    console.error("Error fetching pipeline configs:", error);
    throw error;
  }
};

export const getPipelineConfig = async (modelId: string, configId: string): Promise<TrainingPipelineConfig | null> => {
  try {
    const data = await apiRequest<TrainingPipelineConfig>("GET", `${BASE}/${modelId}/pipeline-configs/${configId}`);
    return data ?? null;
  } catch (error) {
    console.error("Error fetching pipeline config:", error);
    throw error;
  }
};

export const createPipelineConfig = async (
  modelId: string,
  config: TrainingPipelineConfigCreatePayload
): Promise<TrainingPipelineConfig> => {
  try {
    const response = await apiRequest<TrainingPipelineConfig>(
      "POST",
      `${BASE}/${modelId}/pipeline-configs`,
      config as unknown as Record<string, unknown>
    );
    if (!response) throw new Error("Failed to create pipeline config");
    return response;
  } catch (error) {
    console.error("Error creating pipeline config:", error);
    throw error;
  }
};

export const updatePipelineConfig = async (
  modelId: string,
  configId: string,
  config: TrainingPipelineConfigUpdatePayload
): Promise<TrainingPipelineConfig> => {
  try {
    const response = await apiRequest<TrainingPipelineConfig>(
      "PUT",
      `${BASE}/${modelId}/pipeline-configs/${configId}`,
      config as unknown as Record<string, unknown>
    );
    if (!response) throw new Error("Failed to update pipeline config");
    return response;
  } catch (error) {
    console.error("Error updating pipeline config:", error);
    throw error;
  }
};

export const deletePipelineConfig = async (modelId: string, configId: string): Promise<void> => {
  try {
    await apiRequest("DELETE", `${BASE}/${modelId}/pipeline-configs/${configId}`);
  } catch (error) {
    console.error("Error deleting pipeline config:", error);
    throw error;
  }
};

// Pipeline Runs
export const getModelPipelineRuns = async (modelId: string): Promise<PipelineRun[]> => {
  try {
    const data = await apiRequest<PipelineRun[]>("GET", `${BASE}/${modelId}/pipeline-runs`);
    return data || [];
  } catch (error) {
    console.error("Error fetching pipeline runs:", error);
    throw error;
  }
};

export const getPipelineRun = async (modelId: string, runId: string): Promise<PipelineRun | null> => {
  try {
    const data = await apiRequest<PipelineRun>("GET", `${BASE}/${modelId}/pipeline-runs/${runId}`);
    return data ?? null;
  } catch (error) {
    console.error("Error fetching pipeline run:", error);
    throw error;
  }
};

export const createPipelineRun = async (
  modelId: string,
  run: PipelineRunCreatePayload
): Promise<PipelineRun> => {
  try {
    const response = await apiRequest<PipelineRun>(
      "POST",
      `${BASE}/${modelId}/pipeline-runs`,
      run as unknown as Record<string, unknown>
    );
    if (!response) throw new Error("Failed to create pipeline run");
    return response;
  } catch (error) {
    console.error("Error creating pipeline run:", error);
    throw error;
  }
};

export const promotePipelineRun = async (modelId: string, runId: string): Promise<void> => {
  try {
    await apiRequest("POST", `${BASE}/${modelId}/pipeline-runs/${runId}/promote`);
  } catch (error) {
    console.error("Error promoting pipeline run:", error);
    throw error;
  }
};

// Pipeline Artifacts
export const getPipelineRunArtifacts = async (modelId: string, runId: string): Promise<PipelineArtifact[]> => {
  try {
    const data = await apiRequest<PipelineArtifact[]>("GET", `${BASE}/${modelId}/pipeline-runs/${runId}/artifacts`);
    return data || [];
  } catch (error) {
    console.error("Error fetching pipeline artifacts:", error);
    throw error;
  }
};

