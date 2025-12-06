import logging
from enum import Enum
from fastapi import Request
from torch.fx.immutable_collections import immutable_list

from app.core.config.settings import settings


logger = logging.getLogger(__name__)


class ErrorKey(Enum):
    INTERNAL_ERROR = "error_500"
    NOT_FOUND = "not_found"
    SENTIMENT_OBJECT_STRUCTURE = "sentiment_object_structure"
    AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
    OPERATOR_NOT_FOUND = "OPERATOR_NOT_FOUND"
    INVALID_FILE_FORMAT = "invalid_file_format"
    NO_SELECTED_FILE = "no_selected_file"
    INVALID_RECORDED_AT = "invalid_recorded_at"
    RECORDING_NOT_FOUND = "recording_not_found"
    TRANSCRIPT_NOT_FOUND = "transcript_not_found"
    MISSING_TRANSCR_OR_QUEST = "missing_transcr_or_quest"
    FILE_NOT_FOUND = "file_not_found"
    NO_ANALYZED_AUDIO = "no_analyzed_audio"
    MISSING_FIELD_UPLOAD_AUDIO = "missing_field_upload_audio"
    USERNAME_ALREADY_EXISTS = "USERNAME_ALREADY_EXISTS"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    TRANSCRIPT_PARSE_ERROR = "TRANSCRIPT_PARSE_ERROR"
    INVALID_USERNAME_OR_PASSWORD = "INVALID_USERNAME_OR_PASSWORD"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    API_KEY_MISSING = "API_KEY_MISSING"
    INVALID_API_KEY = "INVALID_API_KEY"
    COULD_NOT_VALIDATE_CREDENTIALS = "COULD_NOT_VALIDATE_CREDENTIALS"
    EXPIRED_TOKEN = "EXPIRED_TOKEN"
    NOT_AUTHENTICATED = "NOT_AUTHENTICATED"
    NOT_AUTHORIZED = "NOT_AUTHORIZED"
    ERROR_CREATE_TOKEN = "ERROR_CREATE_TOKEN"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    FILE_TYPE_NOT_ALLOWED = "FILE_TYPE_NOT_ALLOWED"
    FILE_SIZE_TOO_LARGE = "FILE_SIZE_TOO_LARGE"
    MISSING_OPEN_AI_API_KEY = "MISSING_OPEN_AI_API_KEY"
    GPT_RETURNED_INCOMPLETE_RESULT = "GPT_RETURNED_INCOMPLETE_RESULT"
    GPT_FAILED_JSON_PARSING = ("GPT_FAILED_JSON_PARSING",)
    GPT_TRANSCRIPT_QUESTION_ERROR = ("GPT_TRANSCRIPT_QUESTION_ERROR",)
    USER_TYPE_NOT_FOUND = "USER_TYPE_NOT_FOUND"
    ROLE_NOT_FOUND = ("ROLE_NOT_FOUND",)
    INVALID_USER = ("INVALID_USER",)
    API_KEY_NOT_FOUND = ("API_KEY_NOT_FOUND",)
    API_KEY_NAME_EXISTS = "API_KEY_NAME_EXISTS"
    NOT_AUTHORIZED_ACCESS_RESOURCE = "NOT_AUTHORIZED_ACCESS_RESOURCE"
    PERMISSION_NOT_FOUND = "PERMISSION_NOT_FOUND"
    PERMISSION_ALREADY_EXISTS = "PERMISSION_ALREADY_EXISTS"
    ROLE_PERMISSION_NOT_FOUND = "ROLE_PERMISSION_NOT_FOUND"
    ROLE_NOT_ALLOWED = "ROLE_NOT_ALLOWED"
    CONVERSATION_NOT_FOUND = "CONVERSATION_NOT_FOUND"
    CONVERSATIONS_NOT_FOUND = "CONVERSATIONS_NOT_FOUND"
    CONVERSATION_FINALIZED = "CONVERSATION_FINALIZED"
    CONVERSATION_TAKEN_OVER = "CONVERSATION_TAKEN_OVER"
    CONVERSATION_TAKEN_OVER_OTHER = "CONVERSATION_TAKEN_OVER_OTHER"
    DATASOURCE_NOT_FOUND = "DATASOURCE_NOT_FOUND"
    WEBHOOK_NOT_FOUND = "WEBHOOK_NOT_FOUND"
    LLM_PROVIDER_NOT_FOUND = ("LLM_PROVIDER_NOT_FOUND",)
    LLM_ANALYST_NOT_FOUND = "LLM_ANALYST_NOT_FOUND"
    NOT_AUTHORIZED_TO_TAKE_OVER = ("NOT_AUTHORIZED_TO_TAKE_OVER",)
    TOOL_NOT_FOUND = ("TOOL_NOT_FOUND",)
    TOOL_CREATION_FAILED = ("TOOL_CREATION_FAILED",)
    TOOL_UPDATE_FAILED = ("TOOL_UPDATE_FAILED",)
    TOOL_DELETION_FAILED = ("TOOL_DELETION_FAILED",)
    KB_NOT_FOUND = ("KB_NOT_FOUND",)
    AGENT_NOT_ACTIVE = "AGENT_NOT_ACTIVE"
    # MISSING_API_KEY_LLM_PROVIDER = "MISSING_API_KEY_LLM_PROVIDER"
    EMAIL_ALREADY_EXISTS = "EMAIL_ALREADY_EXISTS"
    AGENT_INACTIVE = "AGENT_INACTIVE"
    TRANSCRIPT_ERROR_PARSING = "TRANSCRIPT_ERROR_PARSING"
    APP_SETTINGS_NOT_FOUND = "APP_SETTINGS_NOT_FOUND"
    FEATURE_FLAG_NOT_FOUND = "FEATURE_FLAG_NOT_FOUND"
    WORKFLOW_NOT_FOUND = "WORKFLOW_NOT_FOUND"
    OPERATOR_ROLE_MISSING = ("OPERATOR_ROLE_MISSING",)
    CREATE_USER_TYPE_IN_MENU = "CREATE_USER_TYPE_IN_MENU"
    LOGIN_ERROR_CONSOLE_USER = "LOGIN_ERROR_CONSOLE_USER"
    INVALID_API_KEY_ENCRYPTION = "INVALID_API_KEY_ENCRYPTION"
    CONVERSATION_MUST_START_EMPTY = "CONVERSATION_MUST_START_EMPTY"
    FORCE_PASSWORD_UPDATE = ("FORCE_PASSWORD_UPDATE",)
    MISSING_URL = ("MISSING_URL",)
    INVALID_USER_CONSOLE = ("INVALID_USER_CONSOLE",)
    FINALIZE_LEGRA_NOT_ENABLED = "FINALIZE_LEGRA_NOT_ENABLED"
    REQUIRED_INTERVAL_VALUES = "REQUIRED_INTERVAL_VALUES"
    FAIL_CREATE_EVENT_OFFICE_365 = "FAIL_EVENT_OFFICE_365"
    MISSING_DATA_SOURCE_ID = "MISSING_DATA_SOURCE_ID"
    TOO_MANY_RESULTS = "TOO_MANY_RESULTS"
    FAIL_SEARCH_EVENT_OFFICE_365 = "FAIL_SEARCH_EVENT_OFFICE_365"
    MISSING_PARAMETER = "MISSING_PARAMETER"
    PROVIDER_NOT_SUPPORTED = "PROVIDER_NOT_SUPPORTED"
    ID_CANT_BE_SPECIFIED = "ID_CANT_BE_SPECIFIED"
    FILE_EXTRACT_USAGE = "FILE_EXTRACT_USAGE"
    ERROR_RESPONSE_FORMAT = "ERROR_RESPONSE_FORMAT"
    ERROR_JSON_FORMAT = "ERROR_JSON_FORMAT"
    ERROR_RETURN_WHISPER_SERVICE = "ERROR_RETURN_WHISPER_SERVICE"
    ERROR_TIMEOUT_WHISPER_SERVICE = "ERROR_TIMEOUT_WHISPER_SERVICE"
    ERROR_CONNECTING_WHISPER_SERVICE = "ERROR_CONNECTING_WHISPER_SERVICE"
    ERROR_INSIDE_WHISPER_SERVICE = "ERROR_INSIDE_WHISPER_SERVICE"
    MESSAGE_NOT_FOUND = "MESSAGE_NOT_FOUND"
    ERROR_EXTRACTING_FROM_FILE = "ERROR_EXTRACTING_FROM_FILE"
    ML_MODEL_NOT_FOUND = "ML_MODEL_NOT_FOUND"
    ML_MODEL_NAME_EXISTS = "ML_MODEL_NAME_EXISTS"
    INVALID_PKL_FILE = "INVALID_PKL_FILE"
    PKL_FILE_TOO_LARGE = "PKL_FILE_TOO_LARGE"
    ERROR_UPLOAD_FILE_OPEN_AI = "ERROR_UPLOAD_FILE_OPEN_AI"
    ERROR_CREATE_JOB_OPEN_AI = "ERROR_CREATE_JOB_OPEN_AI"
    ERROR_EXIST_JOB_OPEN_AI = "ERROR_EXIST_JOB_OPEN_AI"
    ERROR_MONITOR_JOB_OPEN_AI = "ERROR_MONITOR_JOB_OPEN_AI"
    ERROR_NON_FINE_TUNED = "ERROR_NON_FINE_TUNED"
    ERROR_DELETE_FILE_JOB_PROG_OPEN_AI = "ERROR_DELETE_JOB_OPEN_AI"
    ERROR_DELETE_FILE_OPEN_AI = "ERROR_DELETE_FILE_OPEN_AI"
    ERROR_CANCEL_JOB_OPEN_AI = "ERROR_CANCEL_JOB_OPEN_AI"
    ERROR_DELETE_MODEL = "ERROR_DELETE_MODEL"
    ERROR_FETCH_FILES_OPEN_AI = ("ERROR_FETCH_FILES_OPEN_AI",)
    ERROR_JOB_OPEN_AI_EVENT = "ERROR_JOB_OPEN_AI_EVENT"
    ERROR_JOB_NOT_FOUND = "ERROR_JOB_NOT_FOUND"
    ERROR_JOB_EVENTS = "ERROR_JOB_EVENTS"
    ERROR_ACTIVE_JOB_EVENTS_SYNC = "ERROR_ACTIVE_JOB_EVENTS_SYNC"
    ERROR_JOB_EVENTS_SYNC = "ERROR_ERROR_JOB_EVENTS_SYNC"
    ERROR_JOB_EVENT_BY_ID = "ERROR_JOB_EVENT_BY_ID"


ERROR_MESSAGES = {
    "en": {
        ErrorKey.INTERNAL_ERROR: "An internal server error occurred. Please try again later.",
        ErrorKey.NOT_FOUND: "The requested resource was not found.",
        ErrorKey.SENTIMENT_OBJECT_STRUCTURE: "Sentiment object must have 'positive', 'neutral', and 'negative' fields.",
        ErrorKey.AGENT_NOT_FOUND: "Agent not found.",
        ErrorKey.INVALID_FILE_FORMAT: "Invalid file format.",
        ErrorKey.NO_SELECTED_FILE: "No selected file",
        ErrorKey.INVALID_RECORDED_AT: "Invalid recorded_at format. Use ISO 8601: YYYY-MM-DDTHH:MM:SSZ",
        ErrorKey.RECORDING_NOT_FOUND: "Recording not found.",
        ErrorKey.TRANSCRIPT_NOT_FOUND: "Transcript not found.",
        ErrorKey.MISSING_TRANSCR_OR_QUEST: "Missing transcror or question.",
        ErrorKey.FILE_NOT_FOUND: "File not found.",
        ErrorKey.NO_ANALYZED_AUDIO: "No analyzed audio data found.",
        ErrorKey.MISSING_FIELD_UPLOAD_AUDIO: "Missing file, agent_id, or recorded_at.",
        ErrorKey.USERNAME_ALREADY_EXISTS: "Username already exists.",
        ErrorKey.USER_NOT_FOUND: "User not found.",
        ErrorKey.OPERATOR_NOT_FOUND: "Operator not found.",
        ErrorKey.TRANSCRIPT_PARSE_ERROR: "There was an error parsing the transcript.",
        ErrorKey.INVALID_USERNAME_OR_PASSWORD: "Invalid username or password.",
        ErrorKey.INSUFFICIENT_PERMISSIONS: "Insufficient permissions for this action.",
        ErrorKey.API_KEY_MISSING: "Api key is required.",
        ErrorKey.INVALID_API_KEY: "Invalid API key.",
        ErrorKey.COULD_NOT_VALIDATE_CREDENTIALS: "Could not validate credentials.",
        ErrorKey.EXPIRED_TOKEN: "Token has expired.",
        ErrorKey.NOT_AUTHENTICATED: "Not authenticated. Provide API Key or Login.",
        ErrorKey.NOT_AUTHORIZED: "Not authorized.",
        ErrorKey.ERROR_CREATE_TOKEN: "Error creating token.",
        ErrorKey.QUOTA_EXCEEDED: "Quota exceeded.",
        ErrorKey.FILE_TYPE_NOT_ALLOWED: f"File type not allowed. Allowed file types: {settings.SUPPORTED_AUDIO_FORMATS}",
        ErrorKey.FILE_SIZE_TOO_LARGE: f"File too large. Max allowed is {settings.MAX_CONTENT_LENGTH // (1024 * 1024)}MB.",
        ErrorKey.MISSING_OPEN_AI_API_KEY: "Missing OpenAI API Key. Set 'OPENAI_API_KEY' as an environment variable.",
        ErrorKey.GPT_RETURNED_INCOMPLETE_RESULT: "Parsing returned incomplete or invalid result.",
        ErrorKey.GPT_FAILED_JSON_PARSING: "Failed to parse GPT response as JSON after multiple attempts.",
        ErrorKey.GPT_TRANSCRIPT_QUESTION_ERROR: "Error while calling GPT for question answering.",
        ErrorKey.USER_TYPE_NOT_FOUND: "User type not found.",
        ErrorKey.ROLE_NOT_FOUND: "Role not found.",
        ErrorKey.INVALID_USER: "Invalid user.",
        ErrorKey.API_KEY_NOT_FOUND: "Api key not found.",
        ErrorKey.API_KEY_NAME_EXISTS: "An API key with this name already exists.",
        ErrorKey.NOT_AUTHORIZED_ACCESS_RESOURCE: "Not authorized to access this resource.",
        ErrorKey.PERMISSION_NOT_FOUND: "Permission not found.",
        ErrorKey.PERMISSION_ALREADY_EXISTS: "Permission already exists.",
        ErrorKey.ROLE_PERMISSION_NOT_FOUND: "Role Permission not found.",
        ErrorKey.ROLE_NOT_ALLOWED: "You're not allowed to assign this role.",
        ErrorKey.CONVERSATION_NOT_FOUND: "Conversation not found.",
        ErrorKey.CONVERSATION_FINALIZED: "Conversation already finalized.",
        ErrorKey.CONVERSATION_TAKEN_OVER: "Conversation already taken over.",
        ErrorKey.CONVERSATION_TAKEN_OVER_OTHER: "Conversation already taken over by another user.",
        ErrorKey.DATASOURCE_NOT_FOUND: "Datasource not found.",
        ErrorKey.LLM_PROVIDER_NOT_FOUND: "LLM Provider not found.",
        ErrorKey.LLM_ANALYST_NOT_FOUND: "LLM Analyst not found.",
        ErrorKey.NOT_AUTHORIZED_TO_TAKE_OVER: "You are not authorized to take over conversations.",
        ErrorKey.TOOL_NOT_FOUND: "Tool not found.",
        ErrorKey.TOOL_CREATION_FAILED: "Tool creation failed.",
        ErrorKey.TOOL_UPDATE_FAILED: "Tool update failed.",
        ErrorKey.TOOL_DELETION_FAILED: "Tool deletion failed.",
        ErrorKey.KB_NOT_FOUND: "KB not found.",
        ErrorKey.AGENT_NOT_ACTIVE: "Agent is not active.",
        # ErrorKey.MISSING_API_KEY_LLM_PROVIDER: "Missing Api Key in connection data.",
        ErrorKey.EMAIL_ALREADY_EXISTS: "Email already exists.",
        ErrorKey.AGENT_INACTIVE: "Agent is inactive.",
        ErrorKey.TRANSCRIPT_ERROR_PARSING: "Couldn't parse transcript, please try again later.",
        ErrorKey.APP_SETTINGS_NOT_FOUND: "App Settings not found.",
        ErrorKey.FEATURE_FLAG_NOT_FOUND: "Feature Flags not found.",
        ErrorKey.OPERATOR_ROLE_MISSING: "Operator role missing.",
        ErrorKey.CREATE_USER_TYPE_IN_MENU: "Operators and ai agents should be created in their specific menus.",
        ErrorKey.LOGIN_ERROR_CONSOLE_USER: "Failed to give access for console type user.",
        ErrorKey.INVALID_API_KEY_ENCRYPTION: "Invalid API key encryption.",
        ErrorKey.CONVERSATION_MUST_START_EMPTY: "Conversation must start empty.",
        ErrorKey.FORCE_PASSWORD_UPDATE: "Please update your password to continue.",
        ErrorKey.MISSING_URL: "Missing URL.",
        ErrorKey.INVALID_USER_CONSOLE: "Invalid user console type.",
        ErrorKey.FINALIZE_LEGRA_NOT_ENABLED: "Cannot finalize knowledge base with legra disabled.",
        ErrorKey.REQUIRED_INTERVAL_VALUES: "The fields hostility_neutral_max and hostility_positive_max are required "
        "when filtering by sentiment.",
        ErrorKey.FAIL_CREATE_EVENT_OFFICE_365: "Failed to create event with office 365.",
        ErrorKey.MISSING_DATA_SOURCE_ID: "Missing data source ID.",
        ErrorKey.TOO_MANY_RESULTS: "Too many results requested, maximum is 100.",
        ErrorKey.FAIL_SEARCH_EVENT_OFFICE_365: "Failed to search event with office 365.",
        ErrorKey.MISSING_PARAMETER: "Missing parameter.",
        ErrorKey.PROVIDER_NOT_SUPPORTED: "The provider is not supported.",
        ErrorKey.ID_CANT_BE_SPECIFIED: "Cant specify id for new conversation.",
        ErrorKey.FILE_EXTRACT_USAGE: "Provide either (path) or (filename and content).",
        ErrorKey.ERROR_RESPONSE_FORMAT: "Invalid response format from service.",
        ErrorKey.ERROR_JSON_FORMAT: "Invalid json format from service.",
        ErrorKey.ERROR_RETURN_WHISPER_SERVICE: "Failed status code from transcription service.",
        ErrorKey.ERROR_TIMEOUT_WHISPER_SERVICE: "Failed to connect to service, timeout.",
        ErrorKey.ERROR_CONNECTING_WHISPER_SERVICE: "Error connecting to transcription service.",
        ErrorKey.ERROR_INSIDE_WHISPER_SERVICE: "An error occurred in transcription service.",
        ErrorKey.MESSAGE_NOT_FOUND: "Message not found.",
        ErrorKey.ERROR_EXTRACTING_FROM_FILE: "Failed to extract text from file.",
        ErrorKey.ML_MODEL_NOT_FOUND: "ML model not found.",
        ErrorKey.ML_MODEL_NAME_EXISTS: "A model with this name already exists.",
        ErrorKey.INVALID_PKL_FILE: "Only .pkl files are allowed.",
        ErrorKey.PKL_FILE_TOO_LARGE: "PKL file too large. Maximum size is 100MB.",
        ErrorKey.ERROR_UPLOAD_FILE_OPEN_AI: "Failed to upload file to OpenAI.",
        ErrorKey.ERROR_CREATE_JOB_OPEN_AI: "Failed to create job openai.",
        ErrorKey.ERROR_EXIST_JOB_OPEN_AI: "Job not found.",
        ErrorKey.ERROR_MONITOR_JOB_OPEN_AI: "There was an error fetching the job.",
        ErrorKey.ERROR_JOB_OPEN_AI_EVENT: "There was an error fetching the job events.",
        ErrorKey.ERROR_DELETE_FILE_JOB_PROG_OPEN_AI: "There was an error deleting the file, job in progress.",
        ErrorKey.ERROR_DELETE_FILE_OPEN_AI: "There was an error deleting the file.",
        ErrorKey.ERROR_CANCEL_JOB_OPEN_AI: "There was an error canceling the job.",
        ErrorKey.ERROR_NON_FINE_TUNED: "Can't delete non fine-tuned model.",
        ErrorKey.ERROR_DELETE_MODEL: "There was an error deleting model.",
        ErrorKey.ERROR_FETCH_FILES_OPEN_AI: "Failed to fetch files from OpenAI.",
        ErrorKey.ERROR_JOB_NOT_FOUND: "Job not found in DB.",
        ErrorKey.ERROR_JOB_EVENTS: "There was an error fetching job events.",
        ErrorKey.ERROR_ACTIVE_JOB_EVENTS_SYNC: "There was an error syncing active job events.",
        ErrorKey.ERROR_JOB_EVENTS_SYNC: "There was an error syncing job events.",
        ErrorKey.ERROR_JOB_EVENT_BY_ID: "There was an error fetching job events for this job id.",
    },
    "fr": {
        ErrorKey.INTERNAL_ERROR: "Une erreur interne du serveur est survenue. Veuillez réessayer plus tard.",
    },
}


def get_error_message(
    error_key: ErrorKey,
    request: Request = None,
    lang: str = "en",
    error_variables: list[str] = immutable_list(),
):
    """
    Retrieves an error message dynamically based on the user's language preference.
    Falls back to DEFAULT_LANGUAGE if no valid language is found.
    """
    # Ensure error_key is a valid Enum
    if not isinstance(error_key, ErrorKey):
        raise ValueError(f"Invalid error key: {error_key}")

    # Fetch language from request (query param or header)
    user_lang = (
        (request.query_params.get("lang") or request.headers.get("Accept-Language"))
        if request
        else lang
    )

    # Use default language if unsupported
    lang = (
        user_lang
        if user_lang in settings.SUPPORTED_LANGUAGES
        else settings.DEFAULT_LANGUAGE
    )

    return (
        ERROR_MESSAGES.get(lang, ERROR_MESSAGES[lang]).get(error_key, error_key.value)
    ).format(*error_variables)


def validate_error_messages():
    """Logs a warning if a language is missing keys instead of failing."""
    base_lang = "en"
    base_keys = set(ERROR_MESSAGES[base_lang].keys())

    for lang, messages in ERROR_MESSAGES.items():
        missing_keys = base_keys - set(messages.keys())
        if missing_keys:
            logger.warning(f"Warning: Missing keys in '{lang}': {missing_keys}")


# TODO uncomment in case we add other languages in the future and want warnings about missing keys
# validate_error_messages()
