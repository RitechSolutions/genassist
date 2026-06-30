import type { ConnectionStatus } from "@/interfaces/connectionStatus.interface";

export interface AudioProvider {
  id: string;
  name: string;
  provider_type: string;
  capability: string;
  connection_data: Record<string, unknown>;
  connection_status?: ConnectionStatus | null;
  is_active: number;
  is_default: number;
  created_at: string;
  updated_at: string;
}

export interface AudioProviderMinimal {
  id: string;
  name: string;
  provider_type: string;
  capability: string;
  is_active: number;
}

export interface AudioProviderNodeSchemas {
  tts: Record<string, {
    display_name: string;
    voices: Array<{ value: string; label: string }>;
    models: Array<{ value: string; label: string }>;
    formats: Array<{ value: string; label: string }>;
    supports_speed: boolean;
  }>;
  stt: Record<string, {
    display_name: string;
    models: Array<{ value: string; label: string }>;
    response_formats: Array<{ value: string; label: string }>;
    supports_temperature: boolean;
  }>;
}
