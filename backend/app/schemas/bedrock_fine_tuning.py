from uuid import UUID

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class CreateBedrockFineTuningJobRequest(BaseModel):
    training_data_s3_uri: str = Field(
        ..., description="s3:// URI of the uploaded JSONL training data"
    )
    base_model_id: str = Field(
        ..., description="Nova base model id (e.g. amazon.nova-micro-v1:0:128k)"
    )
    validation_data_s3_uri: Optional[str] = Field(
        None, description="s3:// URI of the validation JSONL (optional)"
    )
    hyperparameters: Optional[Dict[str, Any]] = Field(
        None, description="Hyperparameters (e.g. epochCount, learningRate)"
    )
    suffix: Optional[str] = Field(
        None,
        max_length=40,
        description="Up to 40 chars used to name the custom model",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "training_data_s3_uri": "s3://my-bucket/bedrock-fine-tuning/training/abc.jsonl",
                "base_model_id": "amazon.nova-micro-v1:0:128k",
                "hyperparameters": {"epochCount": "2"},
                "suffix": "support-bot",
            }
        }


class GenerateBedrockTrainingFileRequest(BaseModel):
    conversation_ids: List[UUID] = Field(
        ..., description="Conversation UUIDs to generate Nova training data from"
    )
    upload_to_s3: bool = Field(
        False, description="Upload generated JSONL to S3 and return the S3 URI"
    )
