"""
Celery tasks for ML model pipeline execution.
"""

import asyncio
import logging
import os
from uuid import UUID
from typing import Dict, Any
from pathlib import Path

from celery import shared_task
from app.dependencies.injector import injector
from app.db.multi_tenant_session import multi_tenant_manager
from app.core.tenant_scope import get_tenant_context
from app.repositories.ml_model_pipeline import (
    MLModelPipelineRunRepository,
    MLModelPipelineArtifactRepository,
)
from app.db.models.ml_model_pipeline import PipelineRunStatus, ArtifactType
from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.repositories.workflow import WorkflowRepository
from app.repositories.ml_models import MLModelsRepository
from app.core.project_path import DATA_VOLUME
from app.schemas.ml_model_pipeline import MLModelPipelineArtifactCreate
from app.tasks.base import run_task_for_all_tenants
from app.core.exceptions.exception_classes import AppException
from app.core.exceptions.error_messages import ErrorKey

logger = logging.getLogger(__name__)


def detect_artifact_type(file_path: str) -> ArtifactType:
    """Detect artifact type based on file extension."""
    ext = Path(file_path).suffix.lower()

    if ext in [".pkl", ".joblib", ".h5", ".onnx"]:
        return ArtifactType.MODEL_FILE
    elif ext in [".json", ".csv"]:
        return ArtifactType.METRICS
    elif ext in [".log", ".txt"]:
        return ArtifactType.LOGS
    elif ext in [".csv", ".parquet", ".json"]:
        return ArtifactType.DATA
    else:
        return ArtifactType.OTHER


def scan_for_artifacts(output_dir: str, run_id: UUID) -> list[Dict[str, Any]]:
    """
    Scan a directory for artifacts and return artifact metadata.

    Returns list of dicts with keys: artifact_path, artifact_name, artifact_type, file_size
    """
    artifacts = []

    if not os.path.exists(output_dir):
        logger.warning(f"Output directory does not exist: {output_dir}")
        return artifacts

    for root, dirs, files in os.walk(output_dir):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                file_size = os.path.getsize(file_path)
                artifact_type = detect_artifact_type(file_path)

                # Create a relative name for display
                artifact_name = os.path.relpath(file_path, output_dir)

                artifacts.append(
                    {
                        "artifact_path": file_path,
                        "artifact_name": artifact_name,
                        "artifact_type": artifact_type,
                        "file_size": file_size,
                    }
                )
            except Exception as e:
                logger.error(f"Error processing artifact {file_path}: {str(e)}")

    return artifacts


async def execute_pipeline_run_async(run_id: UUID):
    """
    Async function to execute a pipeline run.
    This is called from the Celery task.
    """
    # Get tenant session factory based on current tenant context
    tenant_id = get_tenant_context()
    session_factory = multi_tenant_manager.get_tenant_session_factory(tenant_id)

    async with session_factory() as session:
        try:
            run_repository = MLModelPipelineRunRepository(session)
            artifact_repository = MLModelPipelineArtifactRepository(session)
            workflow_repository = WorkflowRepository(session)
            model_repository = MLModelsRepository(session)

            try:
                # Get the pipeline run
                # If run doesn't exist in this tenant's database, skip execution
                # (this happens when run_task_for_all_tenants queries all tenants)
                try:
                    run = await run_repository.get_by_id(run_id)
                except AppException as e:
                    if e.error_key == ErrorKey.NOT_FOUND:
                        logger.info(
                            f"Pipeline run {run_id} not found in tenant {tenant_id}, skipping execution"
                        )
                        return None  # Skip this tenant - run doesn't belong to it
                    raise

                # Update status to running
                await run_repository.update_status(run_id, PipelineRunStatus.RUNNING)

                # Get workflow
                workflow = await workflow_repository.get_by_id(run.workflow_id)
                if not workflow:
                    raise Exception(f"Workflow {run.workflow_id} not found")

                # Get model
                model = await model_repository.get_by_id(run.model_id)

                # Prepare workflow execution input
                workflow_config = {
                    "id": str(run.workflow_id),
                    "nodes": workflow.nodes or [],
                    "edges": workflow.edges or [],
                }

                # Build workflow
                workflow_engine = WorkflowEngine.get_instance()
                workflow_engine.build_workflow(workflow_config)

                # Prepare input data with model context
                input_data = {
                    "model_id": str(run.model_id),
                    "model_name": model.name,
                    "pipeline_run_id": str(run_id),
                }

                # Execute workflow
                thread_id = f"pipeline_run_{run_id}"
                state = await workflow_engine.execute_from_node(
                    str(run.workflow_id), input_data=input_data, thread_id=thread_id
                )

                # Extract execution results
                execution_output = state.format_state_as_response()

                # Determine output directory (typically in datavolume/train/{run_id}/)
                output_dir = str(DATA_VOLUME / "train" / str(run_id))

                # Scan for artifacts
                artifacts = scan_for_artifacts(output_dir, run_id)

                # Create artifact records
                for artifact_data in artifacts:
                    artifact_create = MLModelPipelineArtifactCreate(
                        pipeline_run_id=run_id,
                        artifact_type=artifact_data["artifact_type"],
                        artifact_path=artifact_data["artifact_path"],
                        artifact_name=artifact_data["artifact_name"],
                        file_size=artifact_data["file_size"],
                    )
                    await artifact_repository.create(artifact_create)

                # Update run status to completed
                await run_repository.update_status(
                    run_id,
                    PipelineRunStatus.COMPLETED,
                    execution_output=execution_output,
                    execution_id=UUID(state.execution_id) if state.execution_id else None,
                )

                logger.info(f"Pipeline run {run_id} completed successfully")

            except Exception as e:
                logger.error(
                    f"Error executing pipeline run {run_id}: {str(e)}", exc_info=True
                )

                # Update run status to failed
                # Skip if run doesn't exist in this tenant's database
                try:
                    await run_repository.update_status(
                        run_id, PipelineRunStatus.FAILED, error_message=str(e)
                    )
                except AppException as update_error:
                    if update_error.error_key == ErrorKey.NOT_FOUND:
                        logger.info(
                            f"Pipeline run {run_id} not found in tenant {tenant_id} when updating status, skipping"
                        )
                    else:
                        logger.error(f"Error updating run status: {str(update_error)}")
                except Exception as update_error:
                    logger.error(f"Error updating run status: {str(update_error)}")
        finally:
            # Ensure session is properly closed
            await session.close()


async def execute_pipeline_run_async_with_scope(run_id: UUID):
    """Wrapper to run pipeline execution for all tenants"""
    from app.tasks.base import create_task_wrapper, run_task_for_all_tenants
    
    # Create a wrapper that handles the UUID conversion
    async def task_with_uuid_conversion(**kwargs):
        task_run_id = kwargs.get("run_id", run_id)
        if isinstance(task_run_id, str):
            task_run_id = UUID(task_run_id)
        return await execute_pipeline_run_async(task_run_id)
    
    try:
        logger.info(f"Starting pipeline run execution task for all tenants: {run_id}")
        wrapper = create_task_wrapper(task_with_uuid_conversion)
        results = await run_task_for_all_tenants(wrapper, run_id=str(run_id))
        
        logger.info(f"Pipeline run execution completed for {len(results)} tenant(s)")
        return {
            "status": "success",
            "results": results,
        }
    except Exception as e:
        logger.error(f"Error in pipeline run execution task: {str(e)}")
        return {
            "status": "failed",
            "error": str(e),
        }
    finally:
        logger.info("Pipeline run execution task completed.")


@shared_task(name="execute_pipeline_run")
def execute_pipeline_run_task(run_id: str):
    """
    Celery task to execute a pipeline run asynchronously.

    Args:
        run_id: UUID string of the pipeline run to execute
    """
    logger.info(f"Starting pipeline run execution: {run_id}")

    try:
        # Run the async function
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(execute_pipeline_run_async_with_scope(UUID(run_id)))

    except Exception as e:
        logger.error(f"Error in pipeline run task {run_id}: {str(e)}", exc_info=True)
        raise


async def check_and_execute_scheduled_pipelines_async():
    """
    Check all pipeline configs with cron schedules and execute them if needed.
    This runs periodically to check for scheduled executions.
    """
    from croniter import croniter
    from datetime import datetime, timezone
    from app.repositories.ml_model_pipeline import MLModelPipelineConfigRepository
    from app.schemas.ml_model_pipeline import MLModelPipelineRunCreate

    # Get tenant session factory based on current tenant context
    tenant_id = get_tenant_context()
    session_factory = multi_tenant_manager.get_tenant_session_factory(tenant_id)

    async with session_factory() as session:
        try:
            config_repository = MLModelPipelineConfigRepository(session)
            run_repository = MLModelPipelineRunRepository(session)

            # Get all configs with cron schedules (this would need a new method)
            # For now, we'll get all configs and filter
            # TODO: Add a method to get configs with cron schedules

            # Get all active configs (simplified - in production, add a method to filter by cron_schedule)
            from sqlalchemy import select
            from app.db.models.ml_model_pipeline import MLModelPipelineConfig

            query = select(MLModelPipelineConfig).where(
                MLModelPipelineConfig.cron_schedule.isnot(None),
                MLModelPipelineConfig.is_deleted == 0,
            )
            result = await session.execute(query)
            configs = result.scalars().all()

            current_time = datetime.now(timezone.utc)
            executed_count = 0

            for config in configs:
                if not config.cron_schedule:
                    continue

                try:
                    # Check if it's time to run based on cron schedule
                    cron_iter = croniter(config.cron_schedule, current_time)
                    next_run_time = cron_iter.get_prev(datetime)

                    # Check if we should run (within the last minute)
                    time_diff = (current_time - next_run_time).total_seconds()

                    if 0 <= time_diff < 60:  # Within the last minute
                        # Check if we already ran this recently (avoid duplicates)
                        # Get the last run for this config
                        from sqlalchemy import select
                        from app.db.models.ml_model_pipeline import MLModelPipelineRun

                        last_run_query = (
                            select(MLModelPipelineRun)
                            .where(
                                MLModelPipelineRun.pipeline_config_id == config.id,
                                MLModelPipelineRun.is_deleted == 0,
                            )
                            .order_by(MLModelPipelineRun.created_at.desc())
                            .limit(1)
                        )
                        last_run_result = await session.execute(last_run_query)
                        last_run = last_run_result.scalar_one_or_none()

                        # Only run if last run was more than 1 minute ago or doesn't exist
                        should_run = True
                        if last_run and last_run.created_at:
                            time_since_last_run = (
                                current_time - last_run.created_at
                            ).total_seconds()
                            if time_since_last_run < 60:
                                should_run = False

                        if should_run:
                            # Create a new pipeline run
                            run_data = MLModelPipelineRunCreate(
                                model_id=config.model_id,
                                pipeline_config_id=config.id,
                                workflow_id=config.workflow_id,
                            )

                            run = await run_repository.create(run_data)

                            # Queue async execution (import here to avoid circular imports)
                            from app.tasks.ml_model_pipeline_tasks import (
                                execute_pipeline_run_task,
                            )

                            execute_pipeline_run_task.delay(str(run.id))
                            executed_count += 1
                            logger.info(
                                f"Scheduled pipeline run created: {run.id} for config {config.id}"
                            )

                except Exception as e:
                    logger.error(
                        f"Error checking cron schedule for config {config.id}: {str(e)}"
                    )

            if executed_count > 0:
                logger.info(f"Executed {executed_count} scheduled pipeline runs")

        except Exception as e:
            logger.error(f"Error checking scheduled pipelines: {str(e)}", exc_info=True)
        finally:
            # Ensure session is properly closed
            await session.close()


async def check_and_execute_scheduled_pipelines_async_with_scope():
    """Wrapper to run scheduled pipeline check for all tenants"""
    from app.tasks.base import run_task_with_tenant_support
    return await run_task_with_tenant_support(
        check_and_execute_scheduled_pipelines_async,
        "scheduled pipeline check"
    )


@shared_task
def check_scheduled_pipeline_runs():
    """
    Celery beat task to check for scheduled pipeline runs and execute them.
    This should run every minute.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(
            check_and_execute_scheduled_pipelines_async_with_scope()
        )
    except Exception as e:
        logger.error(f"Error in scheduled pipeline check task: {str(e)}", exc_info=True)
        raise
