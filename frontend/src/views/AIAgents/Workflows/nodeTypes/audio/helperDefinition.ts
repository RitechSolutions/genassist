import type { NodeHelpContent } from "../../types/nodes";

export const AUDIO_NODES_HELP_CONTENT: NodeHelpContent = {
  intro:
    "Audio nodes convert between text and audio formats within a workflow. Use them to generate speech from text or transcribe audio into text.",
  sections: [
    {
      title: "When To Use Audio Nodes",
      body: "Use audio nodes when you need to:",
      bullets: [
        "Convert LLM-generated text into spoken audio",
        "Transcribe audio input into text for further processing",
        "Build voice-enabled workflows that handle both text and audio",
      ],
    },
    {
      title: "Summary",
      body: "Audio nodes act as bridges between text-based and audio-based parts of a workflow. Text to Speech produces audio from text, while Speech to Text transcribes audio back into text.",
    },
  ],
};

export const TTS_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Text to Speech node converts text input into spoken audio using a TTS provider such as OpenAI.",
  sections: [
    {
      title: "How It Works",
      steps: [
        "Connect a text-producing node to the input",
        "Configure the voice, model, and output format",
        "The node generates audio and outputs it for downstream audio-consuming nodes",
      ],
    },
    {
      title: "Configuration",
      bullets: [
        "Voice: Choose from available voices (e.g., Nova, Alloy, Echo)",
        "Model: Select TTS-1 for speed or TTS-1 HD for higher quality",
        "Format: Output as MP3, WAV, FLAC, Opus, AAC, or PCM",
        "Speed: Adjust playback speed from 0.25x to 4.0x",
      ],
    },
  ],
};

export const STT_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Speech to Text node transcribes audio input into text using a transcription provider such as OpenAI Whisper.",
  sections: [
    {
      title: "How It Works",
      steps: [
        "Connect an audio-producing node to the input",
        "Configure the transcription model and language",
        "The node transcribes the audio and outputs text for downstream text-consuming nodes",
      ],
    },
    {
      title: "Configuration",
      bullets: [
        "Model: Choose Whisper-1, GPT-4o Transcribe, or GPT-4o Mini Transcribe",
        "Language: Optionally specify a language code for better accuracy",
        "Format: Get results as plain text, JSON, or verbose JSON with timestamps",
        "Temperature: Control randomness in transcription (0.0 for deterministic)",
      ],
    },
  ],
};
