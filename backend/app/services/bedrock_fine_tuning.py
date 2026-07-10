import asyncio
import json
import logging
from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID, uuid4

import boto3
from injector import inject

from app.core.config.settings import file_storage_settings
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.bi_utils import validate_bytes_size
from app.core.utils.enums.bedrock_fine_tuning_enum import (
    BedrockDeploymentStatus,
    BedrockJobStatus,
)
from app.db.models.fine_tuning import BedrockFineTuningJobModel
from app.repositories.bedrock_fine_tuning import BedrockFineTuningRepository
from app.constants.bedrock_fine_tuning import (
    FINE_TUNABLE_MODELS_SETTING_NAME,
    FINE_TUNABLE_MODELS_SETTING_TYPE,
    NOVA_FINE_TUNABLE_MODELS,
    NOVA_SCHEMA_VERSION,
)
from app.schemas.bedrock_fine_tuning import (
    CreateBedrockFineTuningJobRequest,
    GenerateBedrockTrainingFileRequest,
)
from app.services.app_settings import AppSettingsService
from app.services.open_ai_fine_tuning import OpenAIFineTuningService

logger = logging.getLogger(__name__)


@inject
class BedrockFineTuningService:
    """Fine-tuning of Amazon Nova models through the Bedrock control plane.

    Unlike OpenAI, boto3 is synchronous, so every AWS call is offloaded with
    ``asyncio.to_thread`` to avoid blocking the event loop. Training data lives
    in S3, and the resulting custom model is served on-demand via a Nova custom
    model deployment.
    """

    def __init__(
        self,
        repository: BedrockFineTuningRepository,
        openai_service: OpenAIFineTuningService,
        app_settings_service: AppSettingsService,
    ):
        self.repository = repository
        # Reused for conversation fetching + workflow/tool extraction helpers.
        self.openai_service = openai_service
        self.app_settings_service = app_settings_service
        self.region = file_storage_settings.BEDROCK_FINE_TUNING_REGION
        self.bucket = (
            file_storage_settings.BEDROCK_FINE_TUNING_S3_BUCKET
            or file_storage_settings.AWS_STORAGE_BUCKET
        )

        self._bedrock_client = None
        self._s3_client = None

    # ------------------------------------------------------------------
    # boto3 clients (lazy) + thread offload helper
    # ------------------------------------------------------------------
    @property
    def bedrock(self):
        if self._bedrock_client is None:
            self._bedrock_client = boto3.client("bedrock", region_name=self.region)
        return self._bedrock_client

    @property
    def s3(self):
        if self._s3_client is None:
            self._s3_client = boto3.client("s3", region_name=self.region)
        return self._s3_client

    @staticmethod
    async def _run(fn, /, **kwargs):
        return await asyncio.to_thread(lambda: fn(**kwargs))

    def _require_config(self):
        if not file_storage_settings.BEDROCK_FINE_TUNING_ROLE_ARN or not self.bucket:
            raise AppException(error_key=ErrorKey.ERROR_BEDROCK_NOT_CONFIGURED)

    # ------------------------------------------------------------------
    # Training data (S3)
    # ------------------------------------------------------------------
    async def upload_training_data(self, content: bytes, filename: str) -> str:
        """Store JSONL training data in S3 and return its s3:// URI."""
        self._require_config()
        try:
            validate_bytes_size(content)
            key = f"bedrock-fine-tuning/training/{uuid4()}-{filename}"
            await self._run(
                self.s3.put_object, Bucket=self.bucket, Key=key, Body=content
            )
            s3_uri = f"s3://{self.bucket}/{key}"
            logger.info(f"Uploaded Bedrock training data to {s3_uri}")
            return s3_uri
        except AppException:
            raise
        except Exception as e:
            logger.exception(f"Error uploading Bedrock training data: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_UPLOAD_FILE_BEDROCK)

    # ------------------------------------------------------------------
    # Job lifecycle
    # ------------------------------------------------------------------
    async def create_fine_tuning_job(
        self, job_request: CreateBedrockFineTuningJobRequest
    ) -> BedrockFineTuningJobModel:
        self._require_config()
        try:
            unique = uuid4().hex[:12]
            job_name = f"genassist-ft-{unique}"
            suffix = (job_request.suffix or "nova").replace(" ", "-")[:40]
            # Custom model names must be unique; keep them readable + collision-free.
            custom_model_name = f"{suffix}-{unique}"
            output_s3_uri = f"s3://{self.bucket}/bedrock-fine-tuning/output/{unique}/"

            params: dict[str, Any] = {
                "jobName": job_name,
                "customModelName": custom_model_name,
                "roleArn": file_storage_settings.BEDROCK_FINE_TUNING_ROLE_ARN,
                "baseModelIdentifier": job_request.base_model_id,
                "customizationType": "FINE_TUNING",
                "trainingDataConfig": {"s3Uri": job_request.training_data_s3_uri},
                "outputDataConfig": {"s3Uri": output_s3_uri},
            }
            if job_request.validation_data_s3_uri:
                params["validationDataConfig"] = {
                    "validators": [{"s3Uri": job_request.validation_data_s3_uri}]
                }
            if job_request.hyperparameters:
                # Bedrock expects string-valued hyperparameters.
                params["hyperParameters"] = {
                    k: str(v) for k, v in job_request.hyperparameters.items()
                }

            response = await self._run(
                self.bedrock.create_model_customization_job, **params
            )
            job_arn = response["jobArn"]
            logger.info(f"Created Bedrock customization job {job_arn}")

            return await self.repository.create_job_record(
                job_arn=job_arn,
                job_name=job_name,
                base_model_id=job_request.base_model_id,
                custom_model_name=custom_model_name,
                region=self.region,
                training_data_s3_uri=job_request.training_data_s3_uri,
                validation_data_s3_uri=job_request.validation_data_s3_uri,
                output_s3_uri=output_s3_uri,
                hyperparameters=job_request.hyperparameters,
                suffix=job_request.suffix,
                status=BedrockJobStatus.IN_PROGRESS,
            )
        except AppException:
            raise
        except Exception as e:
            logger.exception(f"Error creating Bedrock fine-tuning job: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_CREATE_JOB_BEDROCK)

    def _map_status(self, bedrock_status: str) -> BedrockJobStatus:
        try:
            return BedrockJobStatus(bedrock_status)
        except ValueError:
            logger.warning(f"Unknown Bedrock job status: {bedrock_status}")
            return BedrockJobStatus.IN_PROGRESS

    async def _sync_job(self, job: BedrockFineTuningJobModel) -> BedrockFineTuningJobModel:
        response = await self._run(
            self.bedrock.get_model_customization_job, jobIdentifier=job.job_arn
        )
        status = self._map_status(response.get("status", "InProgress"))
        end_time = response.get("endTime")
        finished_at = None
        if end_time and status in (
            BedrockJobStatus.COMPLETED,
            BedrockJobStatus.FAILED,
            BedrockJobStatus.STOPPED,
        ):
            finished_at = end_time if isinstance(end_time, datetime) else None

        metrics = response.get("trainingMetrics") or response.get("validationMetrics")
        return await self.repository.update_job_status(
            id=job.id,
            status=status,
            custom_model_arn=response.get("outputModelArn"),
            finished_at=finished_at,
            metrics=metrics,
            error_message=response.get("failureMessage"),
        )

    def _map_deployment_status(self, bedrock_status: str) -> BedrockDeploymentStatus:
        try:
            return BedrockDeploymentStatus(bedrock_status)
        except ValueError:
            logger.warning(f"Unknown Bedrock deployment status: {bedrock_status}")
            return BedrockDeploymentStatus.CREATING

    async def _sync_deployment(
        self, job: BedrockFineTuningJobModel
    ) -> BedrockFineTuningJobModel:
        """Refresh a job's on-demand deployment status from Bedrock.

        No-op unless the job has a deployment ARN. Deployment status is independent
        of the customization job status (a Completed job may still be Creating).
        """
        if not job.deployment_arn:
            return job
        response = await self._run(
            self.bedrock.get_custom_model_deployment,
            customModelDeploymentIdentifier=job.deployment_arn,
        )
        status = self._map_deployment_status(response.get("status", "Creating"))
        failure_message = (
            response.get("failureMessage")
            if status == BedrockDeploymentStatus.FAILED
            else None
        )
        return await self.repository.update_deployment(
            id=job.id,
            deployment_status=status,
            deployment_arn=job.deployment_arn,
            failure_message=failure_message,
        )

    async def get_fine_tuning_job(self, job_id: UUID, sync: bool = False) -> dict:
        try:
            job = await self.repository.get_job_by_id(job_id)
            if not job:
                raise AppException(error_key=ErrorKey.ERROR_JOB_NOT_FOUND)

            should_sync = sync or job.status in (
                BedrockJobStatus.IN_PROGRESS,
                BedrockJobStatus.STOPPING,
            )
            if should_sync:
                job = await self._sync_job(job)
                if (
                    job.deployment_arn
                    and job.deployment_status == BedrockDeploymentStatus.CREATING
                ):
                    job = await self._sync_deployment(job)
            return job.to_dict()
        except AppException:
            raise
        except Exception as e:
            logger.exception(f"Error retrieving Bedrock job {job_id}: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_MONITOR_JOB_BEDROCK)

    async def get_jobs(
        self,
        status: Optional[BedrockJobStatus] = None,
        sync: bool = False,
    ) -> list[dict]:
        try:
            jobs = await self.repository.list_jobs(status=status)
            if sync and jobs:
                synced = []
                for job in jobs:
                    try:
                        if job.status in (
                            BedrockJobStatus.IN_PROGRESS,
                            BedrockJobStatus.STOPPING,
                        ):
                            job = await self._sync_job(job)
                        # Deployment status is independent of job status — refresh it
                        # while a deployment is still being created.
                        if (
                            job.deployment_arn
                            and job.deployment_status == BedrockDeploymentStatus.CREATING
                        ):
                            job = await self._sync_deployment(job)
                    except Exception as e:
                        logger.exception(f"Error syncing Bedrock job {job.job_arn}: {str(e)}")
                    synced.append(job)
                    await asyncio.sleep(0.2)
                jobs = synced
            return [job.to_dict() for job in jobs]
        except Exception as e:
            logger.exception(f"Error listing Bedrock jobs: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_MONITOR_JOB_BEDROCK)

    async def get_all_by_statuses(
        self, statuses: Optional[list[BedrockJobStatus]] = None
    ) -> list[BedrockFineTuningJobModel]:
        return await self.repository.get_jobs_by_status(statuses)

    async def cancel_fine_tuning_job(self, job_id: UUID) -> BedrockFineTuningJobModel:
        try:
            job = await self.repository.get_job_by_id(job_id)
            if not job:
                raise AppException(ErrorKey.ERROR_JOB_NOT_FOUND)

            await self._run(
                self.bedrock.stop_model_customization_job, jobIdentifier=job.job_arn
            )
            return await self.repository.update_job_status(
                id=job.id,
                status=BedrockJobStatus.STOPPING,
            )
        except AppException:
            raise
        except Exception as e:
            logger.exception(f"Error stopping Bedrock job {job_id}: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_CANCEL_JOB_BEDROCK)

    # ------------------------------------------------------------------
    # On-demand deployment (Nova)
    # ------------------------------------------------------------------
    async def deploy_custom_model(self, job_id: UUID) -> BedrockFineTuningJobModel:
        """Create an on-demand custom model deployment for a completed job."""
        try:
            job = await self.repository.get_job_by_id(job_id)
            if not job:
                raise AppException(ErrorKey.ERROR_JOB_NOT_FOUND)
            if job.status != BedrockJobStatus.COMPLETED or not job.custom_model_arn:
                raise AppException(ErrorKey.ERROR_DEPLOY_MODEL_BEDROCK)

            deployment_name = f"{job.custom_model_name}-deployment"[:63]
            response = await self._run(
                self.bedrock.create_custom_model_deployment,
                modelDeploymentName=deployment_name,
                modelArn=job.custom_model_arn,
            )
            deployment_arn = response.get("customModelDeploymentArn")
            return await self.repository.update_deployment(
                id=job.id,
                deployment_status=BedrockDeploymentStatus.CREATING,
                deployment_arn=deployment_arn,
            )
        except AppException:
            raise
        except Exception as e:
            logger.exception(f"Error deploying Bedrock model for job {job_id}: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_DEPLOY_MODEL_BEDROCK)

    async def get_fine_tunable_models(self) -> list[str]:
        """Return the fine-tunable Nova model IDs.

        Reads an App Settings override row (type="Other",
        name="BedrockFineTunableModels", values={"models": [...]}) so the list can
        be changed without a deploy. Falls back to NOVA_FINE_TUNABLE_MODELS when the
        row is absent, empty, or malformed.
        """
        try:
            setting = await self.app_settings_service.get_by_type_and_name(
                FINE_TUNABLE_MODELS_SETTING_TYPE, FINE_TUNABLE_MODELS_SETTING_NAME
            )
            if setting and isinstance(setting.values, dict):
                models = setting.values.get("models")
                if isinstance(models, list) and models:
                    return [str(m) for m in models]
        except Exception as e:
            logger.warning(f"Falling back to default Nova model list: {str(e)}")
        return NOVA_FINE_TUNABLE_MODELS

    # ------------------------------------------------------------------
    # Training file generation from conversations (Nova format)
    # ------------------------------------------------------------------
    def _build_nova_jsonl_entry(
        self, log: Any, messages: list, system_prompt: str
    ) -> dict | None:
        """Build one Nova ``bedrock-conversation-2024`` training example.

        Mirrors OpenAIFineTuningService._build_jsonl_entry for locating the
        user/assistant turns, but emits Nova's text-only conversation schema.
        """
        agent_msg = next(
            (m for m in messages if str(m.id) == str(log.transcript_message_id)), None
        )
        if not agent_msg:
            return None

        user_msg = next(
            (
                m
                for m in messages
                if m.sequence_number == agent_msg.sequence_number - 1
                and m.speaker.lower() in ("customer", "user")
            ),
            None,
        )
        user_text = user_msg.text if user_msg else ""

        try:
            payload = json.loads(log.raw_response)
        except (json.JSONDecodeError, TypeError):
            return None

        row = payload.get("row_agent_response", {})
        final_output = row.get("output", "")
        if not final_output:
            node_execution_status = row.get("state", {}).get("nodeExecutionStatus", {})
            node_statuses = (
                list(node_execution_status.values())
                if isinstance(node_execution_status, dict)
                else node_execution_status
            )
            for ns in node_statuses:
                if ns.get("type") == "agentNode":
                    final_output = (ns.get("output") or {}).get("message", "")
                    if final_output:
                        break

        if not final_output or not user_text:
            return None

        entry: dict = {
            "schemaVersion": NOVA_SCHEMA_VERSION,
            "messages": [
                {"role": "user", "content": [{"text": user_text}]},
                {"role": "assistant", "content": [{"text": str(final_output)}]},
            ],
        }
        if system_prompt:
            entry["system"] = [{"text": system_prompt}]
        return entry

    async def generate_training_file_from_conversations(
        self, request: GenerateBedrockTrainingFileRequest
    ) -> bytes:
        """Generate a Nova JSONL training file from past conversation logs."""
        svc = self.openai_service
        try:
            conversations = await svc.conversation_repo.fetch_conversations_by_ids(
                request.conversation_ids, include_messages=True
            )
            logs_all = await svc.agent_log_repo.get_by_conversation_ids(
                request.conversation_ids
            )

            messages_by_conv: dict[UUID, list] = {
                c.id: sorted(c.messages, key=lambda m: m.sequence_number)
                for c in conversations
            }
            logs_by_conv: dict[UUID, list] = {}
            for log in logs_all:
                logs_by_conv.setdefault(log.conversation_id, []).append(log)

            workflow_cache: dict[UUID, dict] = {}
            jsonl_lines: List[str] = []
            for conversation in conversations:
                operator_id = conversation.operator_id
                if operator_id not in workflow_cache:
                    workflow_cache[operator_id] = await svc._get_workflow_for_operator(
                        operator_id
                    )
                workflow = workflow_cache[operator_id]

                agent_node = svc._extract_agent_node(workflow)
                system_prompt = (
                    agent_node.get("data", {}).get("systemPrompt", "")
                    if agent_node
                    else ""
                )

                messages = messages_by_conv.get(conversation.id, [])
                logs = logs_by_conv.get(conversation.id, [])
                for log in logs:
                    entry = self._build_nova_jsonl_entry(log, messages, system_prompt)
                    if entry is not None:
                        jsonl_lines.append(json.dumps(entry))

            if not jsonl_lines:
                logger.warning(
                    "No valid Nova training examples generated from the conversations"
                )

            result = "\n".join(jsonl_lines).encode("utf-8")
            validate_bytes_size(result)
            return result
        except AppException:
            raise
        except Exception as e:
            logger.exception(f"Error generating Bedrock training file: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_GENERATE_TRAINING_FILE)
