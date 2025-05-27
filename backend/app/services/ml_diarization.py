import os

from pyannote.audio.pipelines.speaker_diarization import SpeakerDiarization


MODEL_PATH = "pyannote/speaker-diarization"
pipeline = SpeakerDiarization.from_pretrained(MODEL_PATH, use_auth_token= os.getenv('HUGGINGFACE_TOKEN'))

def diarize_audio(file_path):
    diarization = pipeline({"uri": file_path, "audio": file_path}, num_speakers=2)

    speaker_segments = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        speaker_segments.append({
            "speaker": speaker,
            "start": turn.start,
            "end": turn.end
        })

    return speaker_segments
