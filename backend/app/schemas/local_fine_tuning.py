from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class LocalFineTuneHyperparameters(BaseModel):
    model_config = ConfigDict(extra="allow")

    num_train_epochs: Optional[float] = None
    per_device_train_batch_size: Optional[int] = None
    gradient_accumulation_steps: Optional[int] = None
    learning_rate: Optional[float] = None
    lora_r: Optional[int] = None
    lora_alpha: Optional[int] = None
    max_seq_length: Optional[int] = None
    logging_steps: Optional[int] = None
    save_steps: Optional[int] = None
    eval_steps: Optional[int] = None
    warmup_steps: Optional[int] = None
    fp16: Optional[bool] = None
    bf16: Optional[bool] = None


class CreateLocalFineTuneJobRequest(BaseModel):
    """Request body for creating a local fine-tuning job. The backend injects `origin`."""

    training_file: str
    file_token: str
    model_id: str
    suffix: Optional[str] = None
    tool_training_mode: Optional[str] = None
    remote_files: bool
    cleanup_files: Optional[bool] = None
    hyperparameters: LocalFineTuneHyperparameters
    gpu_ids: Optional[List[int]] = None


class LocalFineTuneJobError(BaseModel):
    model_config = ConfigDict(extra="allow")

    message: Optional[str] = None
    code: Optional[str] = None


class LocalFineTuneJob(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    status: str
    model: Optional[str] = None
    created_at: Optional[str] = None
    training_file: Optional[str] = None
    validation_file: Optional[str] = None
    hyperparameters: Optional[Dict[str, Any]] = None
    suffix: Optional[str] = None
    finished_at: Optional[str] = None
    fine_tuned_model: Optional[str] = None
    error: Optional[LocalFineTuneJobError] = None


class LocalFineTuneJobEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    job_id: str
    level: str
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: str


class LocalFineTuneSupportedModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str


class GpuInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    name: str
    total_memory_gb: float
    free_memory_gb: float
    used_memory_gb: float
    compute_capability: str


class SystemGpusResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    cuda_available: bool
    gpus: List[GpuInfo] = Field(default_factory=list)


class CreateDeploymentRequest(BaseModel):
    deployment_id: str
    job_id: str
    gpu_id: Optional[int] = None
    tensor_parallel_size: Optional[int] = None
    max_model_len: Optional[int] = None
    gpu_memory_utilization: Optional[float] = None
    dtype: Optional[str] = None


class LocalFineTuneDeployment(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    status: str
    model_path: str
    port: int
    gpu_id: Optional[int] = None
    api_url: str
    created_at: Optional[str] = None
    process_id: Optional[int] = None
    error_message: Optional[str] = None
    max_model_len: Optional[int] = None


class LocalFineTuneDeploymentHealth(BaseModel):
    model_config = ConfigDict(extra="allow")

    deployment_id: str
    status: str
    api_url: str
    details: str


class DeploymentStopResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    status: str
    message: str


class DeleteJobFilesRequest(BaseModel):
    delete_data_files: bool = True
    delete_checkpoints: bool = True
    delete_model: bool = False


class DeleteJobFilesResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    job_id: str
    status: str
    deleted_items: List[str] = Field(default_factory=list)
    bytes_freed: int
    errors: Optional[List[str]] = None
    message: str


class TestInferenceRequest(BaseModel):
    message: str


class TestInferenceResponse(BaseModel):
    content: str