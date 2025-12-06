import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from celery import shared_task
from fastapi_injector import RequestScopeFactory
from io import BytesIO

from app.dependencies.injector import injector
from app.services.datasources import DataSourceService
from app.services.audio import AudioService
from app.services.app_settings import AppSettingsService
from app.schemas.recording import RecordingCreate
from app.db.seed.seed_data_config import SeedTestData
from fastapi import UploadFile

from app.services.smb_share_service import SMBShareFSService 
from app.services.GoogleTranscribeService import GoogleTranscribeService

logger = logging.getLogger(__name__)


@shared_task
def transcribe_audio_files_from_smb():
    """
    Celery task to process audio files from SMB share.
    """
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(transcribe_audio_files_async_with_scope())


async def transcribe_audio_files_async_with_scope(ds_id: Optional[str] = None):
    try:
        logger.info("Starting SMB audio transcription task...")
        request_scope_factory = injector.get(RequestScopeFactory)

        async with request_scope_factory.create_scope():
            result = await transcribe_audio_files_async(ds_id)
            logger.info(f"SMB share/folder transcription task completed: {result}")
            return {"status": "success", "result": result}

    except Exception as e:
        logger.error(f"Error in SMB transcription task: {str(e)}")
        return {"status": "failed", "error": str(e)}

    finally:
        logger.info("SMB transcription task finished.")


async def transcribe_audio_files_async(ds_id: Optional[str] = None):
    dsService = injector.get(DataSourceService)
    audioService = injector.get(AudioService)
    settingsService = injector.get(AppSettingsService)

    google_cloud_json = (await settingsService.get_by_key("google_cloud_json")).model_dump().get("value")
    google_cloud_bucket = (await settingsService.get_by_key("google_cloud_bucket")).model_dump().get("value")
    logger.info(f"google_cloud_json key and google_cloud_bucket is loaded")

    gts = GoogleTranscribeService(sst_region="us-central1", config_json=google_cloud_json, storage_bucket=google_cloud_bucket)

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
            customer_id=None
        )

        # Create SMB session - faling to create object
        async with SMBShareFSService(
            smb_host=smb_host,
            smb_share=smb_share,
            smb_user=smb_user,
            smb_pass=smb_pass,
            smb_port=smb_port,
            local_root=base_folder,
            use_local_fs=use_local_fs
        ) as smb:

            # List *.wav files
            files = await smb.list_dir(
                subpath=base_folder,
                only_files=True,
                pattern="*.wav"
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

                    upload_file = UploadFile(
                        file=BytesIO(content),
                        filename=filename
                    )

                    logger.info(f"Transcribing SMB file: {file_path}")

                    # await audioService.process_recording(upload_file, metadata) # old version with whisper
                    
                    # transcribed_result = gts.transcribe_long_audio(content=content,file_name=filename)
                    # final_transcribed = gts.get_merged_transcripts(transcribed_result)
                    # PROCESSING: save the transcrition
                    await audioService.process_recording_chirp(upload_file, metadata,gts)

                    # Update Statistics
                    transcribed.append({
                        "file": file_path,
                        "timestamp": datetime.now().isoformat()
                    })
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
        "files": transcribed
    }
