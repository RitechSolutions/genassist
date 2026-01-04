from pydub import AudioSegment

def slice_audio(file_path, speaker_segments):
    audio = AudioSegment.from_file(file_path)
    chunks = {}

    for segment in speaker_segments:
        start_time = int(segment["start"] * 1000)  # Convert to milliseconds
        end_time = int(segment["end"] * 1000)

        chunk = audio[start_time:end_time]
        chunks.setdefault(segment["speaker"], []).append(chunk)

    return chunks
