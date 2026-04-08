import asyncio
import logging
from datetime import datetime, timezone
from io import BytesIO
from typing import Optional

from celery import shared_task
from fastapi import UploadFile

from app.db.seed.seed_data_config import SeedTestData
from app.dependencies.injector import injector
from app.schemas.recording import RecordingCreate
from app.services.app_settings import AppSettingsService
from app.services.audio import AudioService
from app.services.datasources import DataSourceService
from app.services.GoogleTranscribeService import GoogleTranscribeService
from app.services.smb_share_service import SMBShareFSService

logger = logging.getLogger(__name__)

def _empty_task_result(*, message: str) -> dict:
    return {
        "datasources": 0,
        "processed": 0,
        "failed": 0,
        "skipped": 0,
        "transcribed": 0,
        "files": [],
        "message": message,
    }


def _extract_setting_value(setting: object) -> Optional[str]:
    values = getattr(setting, "values", None)
    if not isinstance(values, dict) or not values:
        return None
    if "value" in values and values["value"] not in (None, ""):
        return str(values["value"])
    for v in values.values():
        if v not in (None, ""):
            return str(v)
    return None


async def _load_google_cloud_settings_or_none(
    settings_service: AppSettingsService,
) -> Optional[tuple[str, str]]:
    """
    Load Google Cloud config used for transcription.

    Returns None when settings are missing/empty, so the task can skip quietly
    instead of bubbling an exception to the tenant task runner.
    """
    google_cloud_json_setting = await settings_service.get_by_type_and_name(
        "Other", "google_cloud_json"
    )
    google_cloud_bucket_setting = await settings_service.get_by_type_and_name(
        "Other", "google_cloud_bucket"
    )

    if not google_cloud_json_setting or not google_cloud_bucket_setting:
        return None

    google_cloud_json = _extract_setting_value(google_cloud_json_setting)
    google_cloud_bucket = _extract_setting_value(google_cloud_bucket_setting)
    if not google_cloud_json or not google_cloud_bucket:
        return None

    return google_cloud_json, google_cloud_bucket


@shared_task
def transcribe_audio_files_from_smb():
    """
    Celery task to process audio files from SMB share.
    """
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(transcribe_audio_files_async_with_scope())


async def transcribe_audio_files_async_with_scope(ds_id: Optional[str] = None):
    """Wrapper to run SMB transcription for all tenants"""
    from app.tasks.base import run_task_with_tenant_support
    return await run_task_with_tenant_support(
        transcribe_audio_files_async,
        "SMB audio transcription",
        ds_id=ds_id
    )


async def transcribe_audio_files_async(ds_id: Optional[str] = None):
    dsService = injector.get(DataSourceService)
    audioService = injector.get(AudioService)
    settingsService = injector.get(AppSettingsService)

    try:
        gc = await _load_google_cloud_settings_or_none(settingsService)
    except Exception as e:
        logger.error(f"Error getting Google Cloud settings: {e}")
        return _empty_task_result(message=f"Error getting Google Cloud settings: {e}")

    if not gc:
        logger.warning(
            "Skipping SMB transcription: missing/empty Google Cloud settings "
            "('google_cloud_json' and/or 'google_cloud_bucket')"
        )
        return _empty_task_result(
            message="Skipped: missing/empty Google Cloud settings (google_cloud_json/google_cloud_bucket)"
        )

    google_cloud_json, google_cloud_bucket = gc

    logger.info("google_cloud_json key and google_cloud_bucket is loaded")

    gts = GoogleTranscribeService(
        sst_region="us-central1",
        config_json=google_cloud_json,
        storage_bucket=google_cloud_bucket,
    )

    # Load SMB datasources
    if ds_id:
        dsList = [await dsService.get_by_id(ds_id, True)]
    else:
        dsList = await dsService.get_by_type("smb_share_folder", True)

    count_datasource = 0
    count_success = 0
    count_fail = 0
    count_skipped = 0
    transcribed = []

    for ds_item in dsList:
        if ds_item.is_active == 0:
            continue

        count_datasource += 1
        conn = ds_item.connection_data
        logger.info(f"Processing SMB Share/Folder Datasource: {conn}")

        # Required SMB config fields stored in datasource connection_data
        smb_host = conn.get("smb_host")
        smb_share = conn.get("smb_share")
        smb_user = conn.get("smb_user")
        smb_pass = conn.get("smb_pass")
        smb_port = conn.get("smb_port", 445)

        use_local_fs = conn.get("use_local_fs", False)
        # local_root = conn.get("local_root", "")
        base_folder = conn.get("local_root", "")  # e.g. "/recordings"

        metadata = RecordingCreate(
            operator_id=SeedTestData.transcribe_operator_id,
            transcription_model_name=None,
            llm_analyst_speaker_separator_id=SeedTestData.llm_analyst_speaker_separator_id,
            llm_analyst_kpi_analyzer_id=SeedTestData.llm_analyst_kpi_analyzer_id,
            recorded_at=datetime.now(timezone.utc).isoformat(),
            data_source_id=ds_item.id,
            customer_id=None,
        )

        # Create SMB session - faling to create object
        async with SMBShareFSService(
            smb_host=smb_host,
            smb_share=smb_share,
            smb_user=smb_user,
            smb_pass=smb_pass,
            smb_port=smb_port,
            local_root=base_folder,
            use_local_fs=use_local_fs,
        ) as smb:

            # List *.wav files
            files = await smb.list_dir(
                subpath=base_folder, only_files=True, pattern="*.wav"
            )

            if not files:
                logger.info(f"No audio files found in SMB Datasource: {ds_item.name}")
                continue

            for filename in files:
                file_path = f"{base_folder}/{filename}"

                try:
                    # Prevent reprocessing
                    # if await audioService.recording_exists(file_path, ds_item.id):
                    #     logger.info(f"Skipping already processed: {file_path}")
                    #     count_skipped += 1
                    #     continue

                    # Read raw audio bytes from SMB
                    content = await smb.read_file(file_path, binary=True)

                    upload_file = UploadFile(file=BytesIO(content), filename=filename)

                    logger.info(f"Transcribing SMB file: {file_path}")

                    # await audioService.process_recording(upload_file, metadata) # old version with whisper

                    # transcribed_result = gts.transcribe_long_audio(content=content,file_name=filename)
                    # final_transcribed = gts.get_merged_transcripts(transcribed_result)
                    # PROCESSING: save the transcrition
                    await audioService.process_recording_chirp(
                        upload_file, metadata, gts
                    )

                    # Update Statistics
                    transcribed.append(
                        {"file": file_path, "timestamp": datetime.now().isoformat()}
                    )
                    count_success += 1

                except Exception as e:
                    count_fail += 1
                    logger.error(f"Failed to transcribe {file_path}: {str(e)}")

    return {
        "datasources": count_datasource,
        "processed": count_success,
        "failed": count_fail,
        "skipped": count_skipped,
        "transcribed": len(transcribed),
        "files": transcribed,
    }
