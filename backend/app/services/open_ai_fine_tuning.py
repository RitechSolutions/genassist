import asyncio
import json
import logging
from datetime import datetime
from typing import Any, List, Optional
from fastapi import UploadFile
from injector import inject
from openai import AsyncOpenAI
from uuid import UUID

from app.core.config.settings import settings
from app.core.exceptions.error_messages import ErrorKey
from app.core.utils.bi_utils import validate_bytes_size
from app.core.exceptions.exception_classes import AppException
from app.core.utils.date_time_utils import utc_now
from app.core.utils.enums.open_ai_fine_tuning_enum import FileStatus, JobStatus
from app.db.models import FineTuningJobModel
from app.repositories.agent_response_log import AgentResponseLogRepository
from app.repositories.conversations import ConversationRepository
from app.repositories.openai_fine_tuning import FineTuningRepository
from app.schemas.open_ai_fine_tuning import CreateFineTuningJobRequest, GenerateTrainingFileRequest
from app.services.agent_config import AgentConfigService
from app.services.fine_tuning_event import FineTuningEventService


logger = logging.getLogger(__name__)


def _to_snake_case(s: str) -> str:
    """Convert a string to snake_case (mirrors BaseTool.to_snake_case)."""
    final = ""
    for i in range(len(s)):
        item = s[i]
        next_underscored = (
            i < len(s) - 1
            and (s[i + 1] == "_" or s[i + 1] == " " or s[i + 1].isupper())
        )
        if (item == " " or item == "_") and next_underscored:
            continue
        elif item == " " or item == "_":
            final += "_"
        elif item.isupper():
            final += "_" + item.lower()
        else:
            final += item
    return final[1:] if final and final[0] == "_" else final


@inject
class OpenAIFineTuningService:
    def __init__(
        self,
        repository: FineTuningRepository,
        event_service: FineTuningEventService,
        agent_config_service: AgentConfigService,
        agent_log_repo: AgentResponseLogRepository,
        conversation_repo: ConversationRepository,
    ):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.repository = repository
        self.event_service = event_service
        self.agent_config_service = agent_config_service
        self.agent_log_repo = agent_log_repo
        self.conversation_repo = conversation_repo


    async def upload_file(
            self,
            file: UploadFile,
            purpose: str,
            ):
        """
        Upload a file to OpenAI's API and store record in database.

        Args:
            file: The uploaded file
            purpose: Purpose of the file (e.g., "fine-tune", "assistants")

        Returns:
            OpenAI file upload response
        """
        try:
            # Read file content
            file_content = await file.read()

            # Reset file pointer for potential reuse
            await file.seek(0)

            # Upload to OpenAI
            logger.info(f"Uploading file {file.filename} ({len(file_content)} bytes) to OpenAI")

            response = await self.client.files.create(
                    file=(file.filename, file_content),
                    purpose=purpose
                    )

            logger.info(f"Successfully uploaded file to OpenAI. File ID: {response.id}")

            # Store in database and return the DB record so callers have the internal UUID
            db_record = await self.repository.create_file_record(
                    openai_file_id=response.id,
                    filename=response.filename,
                    purpose=response.purpose,
                    bytes=response.bytes,
                    )

            return db_record.to_dict()

        except Exception as e:
            logger.error(f"Error uploading file to OpenAI: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_UPLOAD_FILE_OPEN_AI)


    async def create_fine_tuning_job(
            self,
            job_request: CreateFineTuningJobRequest,
            ):
        """
        Create a fine-tuning job in OpenAI and store record in database.

        Args:
            job_request: Fine-tuning job configuration

        Returns:
            OpenAI fine-tuning job response
        """
        try:
            # Verify training file exists in our DB by internal UUID
            training_file = await self.repository.get_file_by_id(UUID(job_request.training_file))
            if not training_file:
                logger.error(f"Training file {job_request.training_file} not found in database")
                raise AppException(
                        error_key=ErrorKey.ERROR_CREATE_JOB_OPEN_AI
                        )

            # Verify validation file if provided
            validation_file = None
            if job_request.validation_file:
                validation_file = await self.repository.get_file_by_id(UUID(job_request.validation_file))
                if not validation_file:
                    logger.error(f"Validation file {job_request.validation_file} not found in database")
                    raise AppException(
                            error_key=ErrorKey.ERROR_CREATE_JOB_OPEN_AI
                            )

            logger.info(f"Creating fine-tuning job with training_file: {training_file.openai_file_id}")

            # Prepare the request parameters using OpenAI file IDs
            params = {
                "training_file": training_file.openai_file_id,
                "model": job_request.model
                }

            # Add optional parameters if provided
            if validation_file:
                params["validation_file"] = validation_file.openai_file_id
            if job_request.hyperparameters:
                params["hyperparameters"] = job_request.hyperparameters
            if job_request.suffix:
                params["suffix"] = job_request.suffix

            # Create fine-tuning job in OpenAI
            response = await self.client.fine_tuning.jobs.create(**params)

            logger.info(f"Successfully created fine-tuning job. Job ID: {response.id}")

            # Store in database
            job = await self.repository.create_job_record(
                    openai_job_id=response.id,
                    training_file_id=training_file.id,
                    validation_file_id=validation_file.id if validation_file else None,
                    model=response.model,
                    status=JobStatus(response.status),
                    hyperparameters=job_request.hyperparameters,
                    suffix=job_request.suffix,
                    )

            return job

        except AppException:
            raise
        except Exception as e:
            logger.error(f"Error creating fine-tuning job: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_CREATE_JOB_OPEN_AI)


    async def get_fine_tuning_job(self, job_id: UUID, sync: bool = False):
        """
        Retrieve a fine-tuning job by ID with events and progress.

        Args:
            job_id: The fine-tuning job ID
            sync: Whether to sync with OpenAI API (syncs both job status and events)

        Returns:
            Job details with events and progress information
        """
        try:
            logger.info(f"Fetching fine-tuning job: {job_id}")

            # Get job from database
            job_record = await self.repository.get_by_id(job_id, eager=["training_file", "validation_file", "events"])
            if not job_record:
                raise AppException(error_key=ErrorKey.ERROR_EXIST_JOB_OPEN_AI)

            # Determine if we should sync with OpenAI
            should_sync = sync or job_record.status in [
                JobStatus.VALIDATING_FILES,
                JobStatus.QUEUED,
                JobStatus.RUNNING
                ]

            if should_sync:
                # Fetch fresh data from OpenAI
                logger.info(f"Syncing job {job_id} with OpenAI API")
                response = await self.client.fine_tuning.jobs.retrieve(job_record.openai_job_id)

                # Update database with fresh data
                job_record = await self.repository.update_job_status(
                        id=job_record.id,
                        status=JobStatus(response.status),
                        fine_tuned_model=response.fine_tuned_model,
                        finished_at=datetime.fromtimestamp(response.finished_at) if response.finished_at else None,
                        trained_tokens=response.trained_tokens,
                        error_message=response.error.message if response.error else None,
                        error_code=response.error.code if response.error else None
                        )

                # Sync events for active jobs
                try:

                    await self.event_service.sync_events_for_job(job_record.id)
                    logger.info(f"Synced events for job {job_id}")

                    # Refresh to get updated events
                    await self.repository.db.refresh(job_record)
                except Exception as event_error:
                    logger.error(f"Error syncing events for job {job_id}: {str(event_error)}")

                logger.info(f"Retrieved and synced job {job_id}. Status: {response.status}")
            # Build response with events and progress
            job_dict = job_record.to_dict()

            # Attach file details from eager-loaded relationships
            if job_record.training_file:
                job_dict['training_file_info'] = {
                    "id": str(job_record.training_file.id),
                    "openai_file_id": job_record.training_file.openai_file_id,
                    "filename": job_record.training_file.filename,
                    "bytes": job_record.training_file.bytes,
                }
            if job_record.validation_file:
                job_dict['validation_file_info'] = {
                    "id": str(job_record.validation_file.id),
                    "openai_file_id": job_record.validation_file.openai_file_id,
                    "filename": job_record.validation_file.filename,
                    "bytes": job_record.validation_file.bytes,
                }

            # Add events
            self.attach_job_events(job_dict, job_record)

            # Add progress information
            try:
                progress = await self.event_service.get_job_progress(job_record)
                job_dict['progress'] = progress
            except Exception as progress_error:
                logger.error(f"Error getting progress for job {job_id}: {str(progress_error)}")
                job_dict['progress'] = None

            return job_dict

        except Exception as e:
            logger.error(f"Error retrieving fine-tuning job {job_id}: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_MONITOR_JOB_OPEN_AI)


    def attach_job_events(self, job_dict: dict[Any, Any], job_record: FineTuningJobModel):
        job_dict['events'] = [
            {
                "id": str(event.id),
                "openai_event_id": event.openai_event_id,
                "level": event.level,
                "message": event.message,
                "event_created_at": event.event_created_at.isoformat(),
                "metrics": event.metrics,
                "created_at": event.created_at.isoformat()
                }
            for event in job_record.events
            ]


    async def get_all_by_statuses(self, statuses: Optional[list[JobStatus]] = None) -> list[FineTuningJobModel]:
        return await self.repository.get_jobs_by_status(statuses)

    async def get_jobs(
            self,
            status: Optional[JobStatus] = None,
            sync: bool = False
            ):
        """
        List all fine-tuning jobs for a user.

        Args:
            status: Optional status filter
            sync: Whether to sync with OpenAI API (syncs both job status and events)

        Returns:
            List of job records with progress information
        """
        try:
            logger.info(f"Listing jobs, status: {status}, sync: {sync}")
            jobs = await self.repository.list_jobs(status=status)
            logger.info(f"Found {len(jobs)} jobs")

            if sync and jobs:
                logger.info(f"Syncing {len(jobs)} jobs with OpenAI API")

                synced_jobs = []

                for job in jobs:
                    try:
                        # Sync job status
                        response = await self.client.fine_tuning.jobs.retrieve(job.openai_job_id)
                        updated_job = await self.repository.update_job_status(
                                job.id,
                                status=JobStatus(response.status),
                                fine_tuned_model=response.fine_tuned_model,
                                finished_at=datetime.fromtimestamp(
                                        response.finished_at) if response.finished_at else None,
                                trained_tokens=response.trained_tokens,
                                error_message=response.error.message if response.error else None,
                                error_code=response.error.code if response.error else None
                                )
                        synced_jobs.append(updated_job)

                        try:
                            await self.event_service.sync_events_for_job(updated_job.id)
                        except Exception as event_error:
                            logger.error(f"Error syncing events for job {updated_job.id}: {str(event_error)}")

                        await asyncio.sleep(0.2)

                    except Exception as e:
                        logger.error(f"Error syncing job {job.openai_job_id}: {str(e)}")
                        synced_jobs.append(job)

                jobs = synced_jobs
                logger.info(f"Successfully synced {len(synced_jobs)} jobs")

            jobs_with_progress = []
            for job in jobs:
                job_dict = job.to_dict()
                self.attach_job_events(job_dict, job)
                try:
                    progress = await self.event_service.get_job_progress(job)
                    job_dict['progress'] = progress
                except Exception as e:
                    logger.error(f"Error getting progress for job {job.id}: {str(e)}")
                    job_dict['progress'] = None
                jobs_with_progress.append(job_dict)

            return jobs_with_progress

        except Exception as e:
            logger.error(f"Error listing jobs: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_MONITOR_JOB_OPEN_AI)


    async def get_files(self, sync: bool = False):
        """
        List all uploaded files.

        Args:
            sync: Whether to sync with OpenAI API for latest file statuses

        Returns:
            List of file records from database
        """
        try:
            logger.info(f"Listing files, sync: {sync}")

            if sync:
                # Fetch all files from OpenAI
                logger.info("Fetching all files from OpenAI API")
                openai_response = await self.client.files.list()
                openai_files = {file.id: file for file in openai_response.data}
                logger.info(f"Found {len(openai_files)} files in OpenAI")

                # Get files from database
                db_files = await self.repository.list_files_by_user()
                db_files_dict = {file.openai_file_id: file for file in db_files}

                synced_count = 0
                added_count = 0
                deleted_count = 0

                # Update existing files in database
                for file_record in db_files:
                    if file_record.openai_file_id in openai_files:
                        # File exists in OpenAI, update it
                        openai_file = openai_files[file_record.openai_file_id]
                        file_record.status = openai_file.status if hasattr(openai_file,
                                                                           'status') else FileStatus.UPLOADED
                        file_record.bytes = openai_file.bytes
                        file_record.filename = openai_file.filename
                        synced_count += 1
                    else:
                        # File not found in OpenAI, mark as deleted
                        logger.warning(f"File {file_record.openai_file_id} not found in OpenAI")
                        file_record.status = FileStatus.DELETED
                        deleted_count += 1

                # Optional: Add files from OpenAI that aren't in database
                for openai_file_id, openai_file in openai_files.items():
                    if openai_file_id not in db_files_dict:
                        logger.info(f"Found file {openai_file_id} in OpenAI but not in database, adding it")
                        new_file = await self.repository.create_file_record(
                                openai_file_id=openai_file.id,
                                filename=openai_file.filename,
                                purpose=openai_file.purpose,
                                bytes=openai_file.bytes,
                                )
                        db_files.append(new_file)
                        added_count += 1

                await self.repository.db.commit()
                logger.info(
                        f"Sync complete: {synced_count} updated, {added_count} added, {deleted_count} deleted"
                        )

                # Return fresh list
                return await self.repository.list_files_by_user()
            else:
                # No sync, just return database records
                files = await self.repository.list_files_by_user()
                logger.info(f"Found {len(files)} files in database")
                return files

        except Exception as e:
            logger.error(f"Error listing files: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_FETCH_FILES_OPEN_AI)


    async def cancel_fine_tuning_job(self, job_id: UUID):
        """
        Cancel a fine-tuning job.

        Args:
            job_id: The fine-tuning job ID (OpenAI format: ftjob-xxx)

        Returns:
            Updated job record from database
        """
        try:
            logger.info(f"Cancelling fine-tuning job: {job_id}")
            job_record = await self.repository.get_job_by_id(job_id)
            if not job_record:
                raise AppException(ErrorKey.ERROR_JOB_NOT_FOUND)

            # Cancel in OpenAI
            await self.client.fine_tuning.jobs.cancel(job_record.openai_job_id)

            updated_job = await self.repository.update_job_status(
                    job_record.id,
                    status=JobStatus.CANCELLED,
                    finished_at=utc_now(),
                    error_message="Job cancelled by user"
                    )
            logger.info(f"Updated job {job_id} status to CANCELLED in database")
            return updated_job

        except Exception as e:
            logger.error(f"Error cancelling fine-tuning job {job_id}: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_CANCEL_JOB_OPEN_AI)


    async def upload_file_for_chat(
        self,
        file_url: str,
        filename: str,
        purpose: str = "user_data"
    ) -> str:
        """
        Upload a file to OpenAI for use in chat completions.
        
        Args:
            file_url: URL of the file
            filename: Original filename
            purpose: File purpose (default: "user_data" for chat inputs)
        
        Returns:
            OpenAI file ID (e.g., "file-abc123")
        """
        try:
            logger.info(f"Uploading file {filename} from {file_url} to OpenAI for chat")
            
            # Read file content
            with open(file_url, "rb") as f:
                file_content = f.read()
            
            # Upload to OpenAI
            response = await self.client.files.create(
                file=(filename, file_content),
                purpose=purpose
            )
            
            logger.info(f"Successfully uploaded file to OpenAI. File ID: {response.id}")
            
            # Optionally store in database for tracking
            try:
                await self.repository.create_file_record(
                    openai_file_id=response.id,
                    filename=response.filename,
                    purpose=response.purpose,
                    bytes=response.bytes,
                )
            except Exception as db_error:
                # Log but don't fail if DB storage fails
                logger.warning(f"Failed to store file record in DB: {str(db_error)}")
            
            return response.id
            
        except Exception as e:
            logger.error(f"Error uploading file to OpenAI: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_UPLOAD_FILE_OPEN_AI)

    async def delete_file(self, file_id: str):
        """
        Delete a file from OpenAI and update database.

        Args:
            file_id: The OpenAI file ID (format: file-xxx)

        Returns:
            Deletion confirmation
        """
        try:
            logger.info(f"Deleting file: {file_id}")

            # Get file from database first
            file_record = await self.repository.get_file_by_openai_id(file_id)
            if not file_record:
                logger.warning(f"File {file_id} not found in database")
                raise AppException(
                        error_key=ErrorKey.ERROR_DELETE_FILE_JOB_PROG_OPEN_AI,
                        )

            # Check if file is being used in any active jobs
            active_jobs = await self.repository.get_active_jobs()
            for job in active_jobs:
                if job.training_file_id == file_record.id or job.validation_file_id == file_record.id:
                    logger.error(f"File {file_id} is being used in active job {job.openai_job_id}")
                    raise AppException(
                            error_key=ErrorKey.ERROR_DELETE_FILE_JOB_PROG_OPEN_AI,
                            )

            # Delete from OpenAI
            await self.client.files.delete(file_id)

            logger.info(f"Successfully deleted file {file_id} from OpenAI")

            # Update status in database (or delete the record)
            file_record.status = "DELETED"
            await self.repository.db.commit()
            await self.repository.db.refresh(file_record)

            logger.info(f"Updated file {file_id} status to DELETED in database")

            return {
                "id": file_id,
                "object": "file",
                "deleted": True
                }

        except AppException:
            raise
        except Exception as e:
            logger.error(f"Error deleting file {file_id}: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_DELETE_FILE_OPEN_AI)


    def get_fine_tunable_models(self):
        """
        Get list of models that support fine-tuning.
        This is hardcoded based on OpenAI documentation.
        Check https://platform.openai.com/docs/guides/fine-tuning for latest updates.

        Returns:
            List of fine-tunable model names
        """
        # Updated as of October 2024
        fine_tunable_models = [
            "gpt-4o-2024-08-06",
            "gpt-4o-mini-2024-07-18",
            "gpt-4-0613",
            "gpt-3.5-turbo-0125",
            "gpt-3.5-turbo-1106",
            "gpt-3.5-turbo-0613",
            ]

        logger.info(f"Returning {len(fine_tunable_models)} fine-tunable models")
        return fine_tunable_models


    async def delete_fine_tuned_model(self, model_id: str):
        """
        Delete a fine-tuned model from OpenAI.
        Args:
            model_id: The fine-tuned model ID (format: ft:gpt-4o-mini:org:suffix:abc123)

        Returns:
            Deletion confirmation
        """
        try:
            # Validate it's a fine-tuned model
            if not model_id.startswith('ft'):
                logger.error(f"Attempted to delete non-fine-tuned model: {model_id}")
                raise AppException(
                        error_key=ErrorKey.ERROR_NON_FINE_TUNED,
                        )

            logger.info(f"Deleting fine-tuned model: {model_id}")

            # Delete from OpenAI
            _ = await self.client.models.delete(model_id)

            logger.info(f"Successfully deleted model {model_id} from OpenAI")

            # Update database - find the job that created this model
            try:
                job = await self.repository.get_job_by_fine_tuned_model(model_id)  # Singular

                if job:
                    await self.repository.soft_delete(job)
                    logger.info(f"Updated job {job.openai_job_id} that referenced deleted model {model_id}")
                else:
                    logger.info(f"No job found in database for model {model_id}")

            except Exception as db_error:
                logger.warning(f"Failed to update database after model deletion: {str(db_error)}")

            return {
                "id": model_id,
                "object": "model",
                "deleted": True
                }
        except Exception as e:
            logger.error(f"Error deleting fine-tuned model {model_id}: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_DELETE_MODEL)

    # ------------------------------------------------------------------
    # Training file generation from conversations
    # ------------------------------------------------------------------

    def _extract_agent_node(self, workflow: dict) -> dict | None:
        for node in workflow.get("nodes", []):
            if node.get("type") == "agentNode":
                return node
        return None

    def _extract_tool_nodes_for_agent(self, workflow: dict, agent_node_id: str) -> List[dict]:
        node_map = {n["id"]: n for n in workflow.get("nodes", [])}
        tool_nodes = []
        for edge in workflow.get("edges", []):
            if (
                edge.get("target") == agent_node_id
                and "tools" in edge.get("targetHandle", "")
            ):
                source_id = edge.get("source")
                if source_id and source_id in node_map:
                    tool_nodes.append(node_map[source_id])
        return tool_nodes

    def _build_openai_tool_schema(self, tool_node: dict) -> dict:
        data = tool_node.get("data", {})
        snake_name = _to_snake_case(data.get("name", tool_node["id"]))
        raw_schema: dict = data.get("inputSchema", {})
        filtered = {k: v for k, v in raw_schema.items() if "session." not in k}
        properties: dict = {}
        required_fields: List[str] = []
        for param_name, param_def in filtered.items():
            properties[param_name] = {"type": param_def.get("type", "string")}
            if param_def.get("description"):
                properties[param_name]["description"] = param_def["description"]
            if param_def.get("required", False):
                required_fields.append(param_name)
        openai_params: dict = {"type": "object", "properties": properties}
        if required_fields:
            openai_params["required"] = required_fields
        return {
            "type": "function",
            "function": {
                "name": snake_name,
                "description": data.get("description", ""),
                "parameters": openai_params,
            },
        }

    def _build_jsonl_entry(
        self,
        log: Any,
        messages: list,
        system_prompt: str,
        tool_schemas: List[dict],
    ) -> dict | None:
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
        node_execution_status = row.get("state", {}).get("nodeExecutionStatus", {})
        node_statuses = (
            list(node_execution_status.values())
            if isinstance(node_execution_status, dict)
            else node_execution_status
        )

        all_steps: list = []
        final_output = row.get("output", "")
        for ns in node_statuses:
            if ns.get("type") == "agentNode":
                output = ns.get("output") or {}
                if not final_output:
                    final_output = output.get("message", "")
                all_steps.extend(output.get("steps", []))

        tool_call_steps = [s for s in all_steps if s.get("type") == "tool_call"]

        training_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]

        if tool_call_steps:
            tool_calls_payload = [
                {
                    "id": s.get("tool_call_id", f"call_{s.get('step', 0):03d}"),
                    "type": "function",
                    "function": {
                        "name": s["tool_name"],
                        "arguments": json.dumps(s.get("tool_input") or {}),
                    },
                }
                for s in tool_call_steps
            ]
            training_messages.append({"role": "assistant", "tool_calls": tool_calls_payload})
            entry: dict = {"messages": training_messages}
            if tool_schemas:
                entry["tools"] = tool_schemas
            return entry
        else:
            if not final_output:
                return None
            training_messages.append({"role": "assistant", "content": str(final_output)})
            return {"messages": training_messages}

    async def _get_workflow_for_operator(self, operator_id: UUID) -> dict:
        """Resolve the workflow for the agent that belongs to the given operator."""
        from sqlalchemy import select as sa_select
        from app.db.models.agent import AgentModel
        from app.schemas.agent import AgentRead

        result = await self.conversation_repo.db.execute(
            sa_select(AgentModel).where(AgentModel.operator_id == operator_id)
        )
        agent_model = result.scalars().first()
        if not agent_model:
            return {}
        agent_read = await self.agent_config_service.get_by_id_full(agent_model.id)
        return agent_read.workflow or {}

    async def generate_training_file_from_conversations(
        self, request: GenerateTrainingFileRequest
    ) -> bytes:
        """
        Generate a JSONL fine-tuning training file from past conversation logs.

        Derives the agent workflow from each conversation's operator, then builds
        one training example per agent response log found in each conversation.
        """
        try:
            conversations = await self.conversation_repo.fetch_conversations_by_ids(
                request.conversation_ids, include_messages=True
            )
            logs_all = await self.agent_log_repo.get_by_conversation_ids(request.conversation_ids)

            # Group messages and logs by conversation_id for O(1) lookup
            messages_by_conv: dict[UUID, list] = {c.id: sorted(c.messages, key=lambda m: m.sequence_number) for c in conversations}
            logs_by_conv: dict[UUID, list] = {}
            for log in logs_all:
                logs_by_conv.setdefault(log.conversation_id, []).append(log)

            # Cache workflows by operator_id
            workflow_cache: dict[UUID, dict] = {}

            jsonl_lines: List[str] = []
            for conversation in conversations:
                operator_id = conversation.operator_id
                if operator_id not in workflow_cache:
                    workflow_cache[operator_id] = await self._get_workflow_for_operator(operator_id)
                workflow = workflow_cache[operator_id]

                agent_node = self._extract_agent_node(workflow)
                system_prompt = (
                    agent_node.get("data", {}).get("systemPrompt", "") if agent_node else ""
                )
                tool_schemas: List[dict] = []
                if agent_node:
                    tool_nodes = self._extract_tool_nodes_for_agent(workflow, agent_node["id"])
                    tool_schemas = [self._build_openai_tool_schema(t) for t in tool_nodes]

                messages = messages_by_conv.get(conversation.id, [])
                logs = logs_by_conv.get(conversation.id, [])

                for log in logs:
                    entry = self._build_jsonl_entry(log, messages, system_prompt, tool_schemas)
                    if entry is not None:
                        jsonl_lines.append(json.dumps(entry))

            if not jsonl_lines:
                logger.warning("No valid training examples were generated from the provided conversations")

            result = "\n".join(jsonl_lines).encode("utf-8")
            validate_bytes_size(result)
            return result

        except AppException:
            raise
        except Exception as e:
            logger.error(f"Error generating training file: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_GENERATE_TRAINING_FILE)