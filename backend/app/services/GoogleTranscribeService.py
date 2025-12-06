from google.api_core.client_options import ClientOptions
from google.cloud import speech_v2
from google.cloud import speech as cloud_speech
from google.oauth2 import service_account
import os
import json
from typing import Optional, Union
from .GoogleStorageService import GoogleStorageService  # adjust relative import if needed


class GoogleTranscribeService:
    """
    A service for transcribing and diarizing audio using Google Cloud Speech-to-Text v2.

    Args:
        sst_project_id (str): Google Cloud project ID.
        sst_region (str): Region for the Speech-to-Text service (e.g., "us-central1").
        storage_service (GoogleStorageService, optional): Storage helper service.
        storage_bucket (str, optional): Bucket for long audio uploads.
        language_code (str, optional): Defaults to "auto".
        sst_model (str, optional): Defaults to "chirp".
    """

    def __init__(
        self,
        sst_region: str,
        sst_project_id: Optional[str] = None,
        storage_service: Optional[GoogleStorageService] = None,
        storage_bucket: Optional[str] = None,
        language_code: str = "auto",
        sst_model: str = "chirp",
        config_json: Optional[str] = None,
        config_json_file: Optional[str] = None,
    ):
        
        credentials = None
        project_id = None

        if config_json:
            info = json.loads(config_json)
            credentials = service_account.Credentials.from_service_account_info(info)
            project_id = info.get("project_id")
        elif config_json_file:
            credentials = service_account.Credentials.from_service_account_file(config_json_file)
            with open(config_json_file, "r") as f:
                project_id = json.load(f).get("project_id")
        else:
            # default credentials from GOOGLE_APPLICATION_CREDENTIALS or environment
            credentials = None
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT")

        self.PROJECT_ID = sst_project_id or project_id
        self.REGION = sst_region or "us-central1"
        self.storage_service = storage_service
        self.storage_bucket = storage_bucket
        self.language_code = language_code
        self.sst_model = sst_model

        self.client = speech_v2.SpeechClient(
            credentials=credentials, 
            client_options=ClientOptions(api_endpoint=f"{sst_region}-speech.googleapis.com"), 
        )

        if storage_bucket and not storage_service:
            self.storage_service = GoogleStorageService(config_json=config_json, config_json_file = config_json_file, storage_bucket = storage_bucket)

    # ----------------------
    # Short Audio Transcription
    # ----------------------
    def transcribe_short_audio(
        self, file_name: Optional[str] = None, content: Optional[bytes] = None
    ):
        """Transcribes short audio directly or from local file."""
        if not content and not file_name:
            raise ValueError("Either 'content' or 'file_name' must be provided.")

        # Load audio content if not provided
        if not content:
            with open(file_name, "rb") as f:
                content = f.read()

        config = cloud_speech.RecognitionConfig(
            auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
            language_codes=[self.language_code],
            model=self.sst_model,
        )

        request = cloud_speech.RecognizeRequest(
            recognizer=f"projects/{self.PROJECT_ID}/locations/{self.REGION}/recognizers/_",
            config=config,
            content=content,
        )

        print("Starting short audio transcription...")
        response = cloud_speech.SpeechClient(
            client_options=ClientOptions(api_endpoint=f"{self.REGION}-speech.googleapis.com")
        ).recognize(request=request)
        print("OK - Transcription complete.")

        return response

    # ----------------------
    # Long Audio Transcription
    # ----------------------
    def transcribe_long_audio(
        self, file_name: Optional[str] = None, content: Optional[bytes] = None
    ):
        """Uploads long audio to GCS, transcribes it, and cleans up."""
        if not self.storage_service or not self.storage_bucket:
            raise ValueError("storage_service and storage_bucket are required for long audio transcription.")

        if not content and not file_name:
            raise ValueError("Either 'content' or 'file_name' must be provided.")

        # Upload file to GCS
        blob_name = os.path.basename(file_name or "temp_audio.wav")

        # Ensure old file is deleted
        if self.storage_service.file_exists(self.storage_bucket, blob_name):
            self.storage_service.delete_file(self.storage_bucket, blob_name)

        if content:
            # self.storage_service.upload_bytes(self.storage_bucket, blob_name, content)
            self.storage_service.file_upload_content(local_file_content=content,local_file_name=blob_name, destination_name=blob_name, prefix="uploads")
        else:
            # self.storage_service.upload_file(self.storage_bucket, file_name, blob_name)
            self.storage_service.file_upload(local_file_path=file_name, destination_name=blob_name, prefix="uploads")

        print(self.storage_service.file_list())

        gcs_uri = f"gs://{self.storage_bucket}/uploads/{blob_name}"

        config = speech_v2.types.RecognitionConfig(
            auto_decoding_config=speech_v2.types.AutoDetectDecodingConfig(),
            language_codes=[self.language_code],
            model=self.sst_model,
        )

        request = speech_v2.types.BatchRecognizeRequest(
            recognizer=f"projects/{self.PROJECT_ID}/locations/{self.REGION}/recognizers/_",
            config=config,
            files=[speech_v2.types.BatchRecognizeFileMetadata(uri=gcs_uri)],
            recognition_output_config=speech_v2.types.RecognitionOutputConfig(
                inline_response_config=speech_v2.types.InlineOutputConfig()
            ),
        )

        print(f"Starting transcription for {gcs_uri}")
        operation = self.client.batch_recognize(request=request)
        response = operation.result(timeout=3600)
        print("OK - Transcription complete.")

        # Cleanup
        #self.storage_service.delete_file(self.storage_bucket, blob_name)
        self.storage_service.file_delete(filename=blob_name, prefix="uploads")

        return response

    # ----------------------
    # Diarization
    # ----------------------
    def diarize_audio(
        self, file_name: Optional[str] = None, content: Optional[bytes] = None
    ):
        """Performs speaker diarization for long audio."""
        if not self.storage_service or not self.storage_bucket:
            raise ValueError("storage_service and storage_bucket are required for diarization.")

        if not content and not file_name:
            raise ValueError("Either 'content' or 'file_name' must be provided.")

        blob_name = os.path.basename(file_name or "temp_audio.wav")

        # Ensure no stale file remains
        if self.storage_service.file_exists(self.storage_bucket, blob_name):
            self.storage_service.delete_file(self.storage_bucket, blob_name)

        if content:
            # self.storage_service.upload_bytes(self.storage_bucket, blob_name, content)
            self.storage_service.file_upload_content(local_file_content=content,local_file_name=blob_name, destination_name=blob_name, prefix="uploads")
        else:
            # self.storage_service.upload_file(self.storage_bucket, file_name, blob_name)
            self.storage_service.file_upload(local_file_path=blob_name, destination_name=blob_name, prefix="uploads")

        print(self.storage_service.file_list())

        gcs_uri = f"gs://{self.storage_bucket}/{blob_name}"

        config = speech_v2.types.RecognitionConfig(
            auto_decoding_config=speech_v2.types.AutoDetectDecodingConfig(),
            language_codes=[self.language_code],
            model=self.sst_model,
            features=speech_v2.types.RecognitionFeatures(
                enable_automatic_punctuation=True,
                enable_word_time_offsets=True,
                diarization_config=speech_v2.types.SpeakerDiarizationConfig(
                    min_speaker_count=1,
                    max_speaker_count=6,
                ),
            ),
        )

        request = speech_v2.types.BatchRecognizeRequest(
            recognizer=f"projects/{self.PROJECT_ID}/locations/{self.REGION}/recognizers/_",
            config=config,
            files=[speech_v2.types.BatchRecognizeFileMetadata(uri=gcs_uri)],
            recognition_output_config=speech_v2.types.RecognitionOutputConfig(
                inline_response_config=speech_v2.types.InlineOutputConfig()
            ),
        )

        print(f"Starting diarized transcription for {gcs_uri}")
        operation = self.client.batch_recognize(request=request)
        response = operation.result(timeout=3600)
        print("OK - Diarization complete.")

        # Cleanup
        self.storage_service.delete_file(self.storage_bucket, blob_name)

        return response


    def get_merged_transcripts(self, response) -> str:
        """
        Merge all transcript alternatives from a Speech-to-Text v2 BatchRecognizeResponse
        into a single concatenated string.

        Args:
            response: The BatchRecognizeResponse (protobuf) from speech_v2.SpeechClient.batch_recognize()

        Returns:
            str: Full merged transcript
        """
        transcripts = []
        lang_code = ""
        full_text=""
        try:
                
            # Iterate through files in response
            for file_key, file_result in response.results.items():
                # Check inline recognition results (preferred)
                inline_response = file_result.transcript

                if inline_response and inline_response.results:
                    for result in inline_response.results:
                        if result.alternatives:
                            transcripts.append(result.alternatives[0].transcript.strip())
                            # print(result.language_code)
                            lang_code=result.language_code

                # Fallback to outer transcript object if inline missing
                elif file_result.transcript and file_result.transcript.results:
                    for result in file_result.transcript.results:
                        if result.alternatives:
                            transcripts.append(result.alternatives[0].transcript.strip())
                            # print(result.language_code)
                            lang_code=result.language_code

            # Merge with space (you can use ". " if you want sentence separation)
            full_text = " ".join(t for t in transcripts if t)

        except Exception as e:
            # fail gracefully and print error to console 
            print(f"Error converting output: {e}")

        return_result = {
            "text":full_text.strip(),
            "language":lang_code, 
            "original_output":response
        }

        return return_result

##############################################
# usage
##############################################
# #Initialize Service
# google_json_config = {
#         "type": "service_account",
#         "project_id": "genassist-stt",
#         ....
#         "client_email": "stt-service@genassist-stt.iam.gserviceaccount.com",
#         "token_uri": "https://oauth2.googleapis.com/token"
#     }
#
# gsc = GoogleStorageService(
#     config_json=json.dumps(google_json_config ),
#     storage_bucket="genassist-stt-audio-bucket"
# )
# gts = GoogleTranscribeService(
#     config_json=json.dumps(google_json_config),
#     storage_bucket="genassist-stt-audio-bucket",
#     storage_service = gsc,
#     sst_region=_region
# )


# # Transcribe File
# result= gts.transcribe_long_audio(file_name=local_file)

# # Convert result in wisper compatibile format
# result_whisper = gts.get_merged_transcripts(result)
