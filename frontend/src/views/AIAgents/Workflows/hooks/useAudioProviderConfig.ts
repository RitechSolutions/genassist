import { useQuery } from "@tanstack/react-query";
import { getAudioProvidersByCapability, getAudioProviderNodeSchemas } from "@/services/audioProviders";
import type { AudioProvider } from "@/interfaces/audioProvider.interface";

interface SelectOption {
  value: string;
  label: string;
}

interface UseAudioProviderConfigOptions {
  capability: "stt" | "tts";
  audioProviderId: string;
  enabled: boolean;
}

interface STTConfig {
  capability: "stt";
  providers: AudioProvider[] | undefined;
  selectedProvider: AudioProvider | undefined;
  providerType: string | undefined;
  models: SelectOption[];
  responseFormats: SelectOption[];
  supportsTemperature: boolean;
  getDefaultsForProvider: (id: string) => { model: string; responseFormat: string } | null;
}

interface TTSConfig {
  capability: "tts";
  providers: AudioProvider[] | undefined;
  selectedProvider: AudioProvider | undefined;
  providerType: string | undefined;
  models: SelectOption[];
  voices: SelectOption[];
  formats: SelectOption[];
  supportsSpeed: boolean;
  getDefaultsForProvider: (id: string) => { voice: string; model: string; outputFormat: string } | null;
}

const DEFAULT_STT_MODELS: SelectOption[] = [
  { value: "whisper-1", label: "Whisper-1" },
  { value: "gpt-4o-transcribe", label: "GPT-4o Transcribe" },
  { value: "gpt-4o-mini-transcribe", label: "GPT-4o Mini Transcribe" },
];

const DEFAULT_STT_RESPONSE_FORMATS: SelectOption[] = [
  { value: "text", label: "Plain Text" },
  { value: "json", label: "JSON" },
  { value: "verbose_json", label: "Verbose JSON" },
];

const DEFAULT_TTS_VOICES: SelectOption[] = [
  { value: "alloy", label: "Alloy" },
  { value: "echo", label: "Echo" },
  { value: "fable", label: "Fable" },
  { value: "onyx", label: "Onyx" },
  { value: "nova", label: "Nova" },
  { value: "shimmer", label: "Shimmer" },
];

const DEFAULT_TTS_MODELS: SelectOption[] = [
  { value: "tts-1", label: "TTS-1 (Fast)" },
  { value: "tts-1-hd", label: "TTS-1 HD (Quality)" },
];

const DEFAULT_TTS_FORMATS: SelectOption[] = [
  { value: "mp3", label: "MP3" },
  { value: "opus", label: "Opus" },
  { value: "aac", label: "AAC" },
  { value: "flac", label: "FLAC" },
  { value: "wav", label: "WAV" },
  { value: "pcm", label: "PCM" },
];

export function useAudioProviderConfig(options: UseAudioProviderConfigOptions & { capability: "stt" }): STTConfig;
export function useAudioProviderConfig(options: UseAudioProviderConfigOptions & { capability: "tts" }): TTSConfig;
export function useAudioProviderConfig({ capability, audioProviderId, enabled }: UseAudioProviderConfigOptions): STTConfig | TTSConfig {
  const { data: audioProviders } = useQuery({
    queryKey: ["audioProviders", capability],
    queryFn: () => getAudioProvidersByCapability(capability),
    enabled,
  });

  const { data: nodeSchemas } = useQuery({
    queryKey: ["audioProviderNodeSchemas"],
    queryFn: getAudioProviderNodeSchemas,
    enabled,
  });

  const selectedProvider = audioProviders?.find((p) => p.id === audioProviderId);
  const providerType = selectedProvider?.provider_type;

  if (capability === "stt") {
    const sttSchema = providerType && nodeSchemas?.stt?.[providerType];
    return {
      capability: "stt",
      providers: audioProviders,
      selectedProvider,
      providerType,
      models: sttSchema?.models || DEFAULT_STT_MODELS,
      responseFormats: sttSchema?.response_formats || DEFAULT_STT_RESPONSE_FORMATS,
      supportsTemperature: sttSchema?.supports_temperature ?? true,
      getDefaultsForProvider: (id: string) => {
        const provider = audioProviders?.find((p) => p.id === id);
        const pType = provider?.provider_type;
        const schema = pType && nodeSchemas?.stt?.[pType];
        if (!schema) return null;
        return {
          model: schema.models[0]?.value || "whisper-1",
          responseFormat: schema.response_formats[0]?.value || "text",
        };
      },
    };
  }

  const ttsSchema = providerType && nodeSchemas?.tts?.[providerType];
  return {
    capability: "tts",
    providers: audioProviders,
    selectedProvider,
    providerType,
    voices: ttsSchema?.voices || DEFAULT_TTS_VOICES,
    models: ttsSchema?.models || DEFAULT_TTS_MODELS,
    formats: ttsSchema?.formats || DEFAULT_TTS_FORMATS,
    supportsSpeed: ttsSchema?.supports_speed ?? true,
    getDefaultsForProvider: (id: string) => {
      const provider = audioProviders?.find((p) => p.id === id);
      const pType = provider?.provider_type;
      const schema = pType && nodeSchemas?.tts?.[pType];
      if (!schema) return null;
      return {
        voice: schema.voices[0]?.value || "nova",
        model: schema.models[0]?.value || "tts-1",
        outputFormat: schema.formats[0]?.value || "mp3",
      };
    },
  };
}
