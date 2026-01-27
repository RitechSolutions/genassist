import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from app.dependencies.injector import injector
from app.core.utils.s3_utils import S3Client
from app.services.datasources import DataSourceService
from celery import shared_task
from io import BytesIO
from app.services.audio import AudioService
from app.db.seed.seed_data_config import SeedTestData
from app.schemas.recording import RecordingCreate

from fastapi import UploadFile

logger = logging.getLogger(__name__)

############################################
#  Transcribe Audio files from the S3 Bucket
############################################


@shared_task
def transcribe_audio_files_from_s3():
    """
    Celery task that Transcribes Audio files from S3 bucket into recordings.
    """
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(transcribe_audio_files_async_with_scope())


async def transcribe_audio_files_async_with_scope(ds_id: Optional[str] = None):
    """Wrapper to run transcription for all tenants"""
    from app.tasks.base import run_task_with_tenant_support
    return await run_task_with_tenant_support(
        transcribe_audio_files_async,
        "S3 audio transcription",
        ds_id=ds_id
    )


async def transcribe_audio_files_async(ds_id: Optional[str] = None):
    # Fetch S3 config from Datasouce

    dsService = injector.get(DataSourceService)
    dsList = []
    if not ds_id:
        dsList = await dsService.get_by_type("S3", True)
    else:
        dsList = [await dsService.get_by_id(ds_id, True)]

    # initialize counter
    count_datasource = 0
    count_transctibed_sucess = 0
    count_transcribed_fail = 0
    count_files_skipped = 0

    audioService = injector.get(AudioService)

    for ds_item in dsList:
        if ds_item.is_active == 0:
            continue

        count_datasource += 1
        conn_data = ds_item.connection_data
        logger.info(f"Processing S3 Datasource: {conn_data}")

        prefix = conn_data["prefix"]
        bucket = conn_data["bucket_name"]
        access_key = conn_data["access_key"]
        secret_key = conn_data["secret_key"]
        region = conn_data["region"]

        s3_client = S3Client(
            bucket_name=bucket,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        metadata = RecordingCreate(
            operator_id=SeedTestData.transcribe_operator_id,
            transcription_model_name=None,
            llm_analyst_speaker_separator_id=SeedTestData.llm_analyst_speaker_separator_id,
            llm_analyst_kpi_analyzer_id=SeedTestData.llm_analyst_kpi_analyzer_id,
            recorded_at=datetime.now(timezone.utc).isoformat(),
            data_source_id=ds_item.id,
            customer_id=None,
        )
        # List audio files (e.g., .wav, .mp3) for current S3 Data Source Bucket
        result = s3_client.list_files(prefix=prefix or "audio/")
        audio_files = [
            f for f in result["files"] if f["key"].endswith((".mp3", ".m4a"))
        ]

        if not audio_files:
            logger.info(f"No audio files found for S3 Datasource: {ds_item.name}")
            continue

        transcribed = []

        for file_info in audio_files:
            try:
                # TODO: if file is already processed skip it (if there is record in recordings)
                # read list of files from S3
                if await audioService.recording_exists(file_info["key"], ds_item.id):
                    logger.info(
                        f"Recording: {file_info['key']} of Datasource {ds_item.name} already processed!!!"
                    )
                    count_files_skipped += 1
                    continue

                content = s3_client.get_file_content(file_info["key"])

                # Convert to UploadFile
                upload_file = UploadFile(
                    file=BytesIO(content),  # in-memory stream
                    filename=file_info["key"],  # ,
                    # content_type="application/octet-stream"
                )

                logger.info(
                    f"Transcribing file: {file_info['key']} of Datasource {ds_item.name}"
                )
                # transcript = await transcribe_audio_whisper_no_save(upload_file)

                transcribed_recording = await audioService.process_recording(
                    upload_file, metadata
                )

                logger.info(f"Transcription for {file_info['key']}: completed")

                # TODO: save it in Recording

                transcribed.append(
                    {"file": file_info["key"], "timestamp": datetime.now().isoformat()}
                )
                count_transctibed_sucess += 1
            except Exception as e:
                count_transcribed_fail += 1
                logger.error(f"Failed to transcribe {file_info['key']}: {str(e)}")
                continue

        return {
            "datasources": count_datasource,
            "processed": count_transctibed_sucess,
            "failed": count_transcribed_fail,
            "skipped": count_files_skipped,
            "transcribed": len(transcribed),
            "files": transcribed,
        }
