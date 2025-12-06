from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class Hyperparameters(BaseModel):
    n_epochs: Optional[int] = Field(None, description="Number of epochs to train for")
    batch_size: Optional[int] = Field(None, description="Batch size for training")
    learning_rate_multiplier: Optional[float] = Field(None, description="Learning rate multiplier")


class CreateFineTuningJobRequest(BaseModel):
    training_file: str = Field(..., description="The ID of the uploaded training file")
    model: str = Field(..., description="The model to fine-tune (e.g., gpt-4.1-nano-2025-04-14)")
    validation_file: Optional[str] = Field(None, description="The ID of the uploaded validation file")
    hyperparameters: Optional[Dict[str, Any]] = Field(None, description="Hyperparameters for fine-tuning")
    suffix: Optional[str] = Field(None, max_length=40, description="A string of up to 40 characters for the fine-tuned model name")

    class Config:
        json_schema_extra = {
            "example": {
                "training_file": "file-RCnFCYRhFDcq1aHxiYkBHw",
                "model": "gpt-4.1-nano-2025-04-14",
                "hyperparameters": {
                    "n_epochs": 3
                }
            }
        }


class FineTuningJobResponse(BaseModel):
    id: str
    object: str
    model: str
    created_at: int
    finished_at: Optional[int] = None
    fine_tuned_model: Optional[str] = None
    organization_id: str
    result_files: List[str]
    status: str
    validation_file: Optional[str] = None
    training_file: str
    hyperparameters: Optional[Dict[str, Any]] = None
    trained_tokens: Optional[int] = None
    error: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True