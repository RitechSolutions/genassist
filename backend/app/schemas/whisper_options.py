from pydantic import BaseModel, Field
from typing import Optional, Literal, Union, Tuple


class WhisperOptions(BaseModel):
    """Options for Whisper transcription with defaults and descriptions."""
    
    # Basic options
    language: Optional[str] = Field(
        None, 
        description="Language code (e.g., 'en', 'es', 'fr') or None for auto-detection"
    )
    task: Literal["transcribe", "translate"] = Field(
        "transcribe", 
        description="Task type: transcribe audio or translate to English"
    )
    temperature: Union[float, Tuple[float, ...]] = Field(
        0.0, 
        description="Sampling temperature (0.0-1.0). Higher values increase randomness"
    )
    
    # Advanced options
    initial_prompt: Optional[str] = Field(
        None, 
        description="Initial prompt to guide transcription style and context"
    )
    word_timestamps: bool = Field(
        False, 
        description="Generate word-level timestamps in addition to segment-level"
    )
    condition_on_previous_text: bool = Field(
        True, 
        description="Use previous text segments for context (improves consistency)"
    )
    compression_ratio_threshold: float = Field(
        2.4, 
        description="Threshold for detecting repetitive text (default: 2.4)"
    )
    logprob_threshold: float = Field(
        -1.0, 
        description="Log probability threshold for segment filtering (default: -1.0)"
    )
    no_speech_threshold: float = Field(
        0.6, 
        description="Silence detection threshold (0.0-1.0, default: 0.6)"
    )
    verbose: bool = Field(
        False, 
        description="Enable verbose output during transcription"
    )
    best_of: Optional[int] = Field(
        None, 
        description="Number of candidates when sampling (default: 5)"
    )
    beam_size: Optional[int] = Field(
        None, 
        description="Number of beams in beam search (default: 5)"
    )
    patience: Optional[float] = Field(
        None, 
        description="Patience value for beam decoding"
    )
