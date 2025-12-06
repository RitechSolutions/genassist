import os
import time
import whisper
import requests
import warnings

# Suppress Whisper's CPU FP16 warning
warnings.filterwarnings("ignore", message="FP16 is not supported on CPU; using FP32 instead")

AUDIO_DIR = "/recordings"
TRANSCRIPTS_DIR = "/recordings/transcripts"
API_ENDPOINT = "http://localhost/analyze-transcript"  # localhost:8000 within internal network
API_TOKEN = ""  # if not needed - not required in internal network

os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)
model = whisper.load_model("base")  # You can change to 'small', 'medium', or 'large'

def is_audio_file(filename):
    return filename.lower().endswith((".mp3", ".wav", ".m4a"))

def find_audio_files(root_dir):
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if is_audio_file(filename):
                yield os.path.join(dirpath, filename)

def post_transcript(transcript_text, metadata):
    headers = {
        "Content-Type": "application/json",
    }
    if API_TOKEN!="":
        headers["Authorization"] = f"Bearer {API_TOKEN}"
    payload = {
        "transcript": transcript_text,
        "metadata": metadata
    }

    try:
        response = requests.post(API_ENDPOINT, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        print(f"Transcript {payload.metadata.filename} posted successfully: {response.status_code}")
    except requests.RequestException as e:
        print(f"Failed to post transcript {payload.metadata.filename}!!!: {e}")

def transcript_exists(filepath):
    relative_path = os.path.relpath(filepath, AUDIO_DIR)
    output_path = os.path.join(TRANSCRIPTS_DIR, relative_path + ".txt")
    return os.path.exists(output_path)

def transcribe_file(filepath):
    print(f"Transcribing: {filepath}")
    result = model.transcribe(filepath)
    text = result["text"]

    # Save to disk
    relative_path = os.path.relpath(filepath, AUDIO_DIR)
    output_path = os.path.join(TRANSCRIPTS_DIR, relative_path + ".txt")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Transcript saved to: {output_path}")

    # Send to API
    metadata = {
        "filename": os.path.basename(filepath),
        "path": relative_path,
        "language": result.get("language", "unknown"),
    }
    post_transcript(text, metadata)

def main():
    processed = set()
    while True:
        for filepath in find_audio_files(AUDIO_DIR):
            if filepath in processed or transcript_exists(filepath):
                continue
            try:
                transcribe_file(filepath)
                processed.add(filepath)
            except Exception as e:
                print(f"Error processing {filepath}: {e}")
        time.sleep(5)

if __name__ == "__main__":
    main()