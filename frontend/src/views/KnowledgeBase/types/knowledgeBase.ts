import { LegacyRagConfig } from "../utils/ragDefaults";

export interface UploadResult {
    file_url?: string;
    file_type?: string;
    file_path: string;
    filename: string;
    original_filename: string;
    file_id?: string;
  }

  export interface FileItem {
    file_id?: string;
    file_path: string;
    original_file_name: string;
    url?: string;
    file_type?: string;
  }

  export interface KnowledgeItem {
    id: string;
    name: string;
    description: string;
    content: string;
    type: "text" | "file" | "url" | "s3" | "sharepoint" | "smb_share_folder" | "azure_blob" | "google_bucket" | "zendesk";
    sync_source_id: string;
    llm_provider_id?: string | null;
    sync_schedule?: string;
    sync_active?: boolean;
    files?: (string | FileItem)[];
    rag_config?: LegacyRagConfig;
    urls?: string[];
    use_http_request?: boolean;
    extra_metadata?: Record<string, unknown>;
    processing_filter?: string | null;
    llm_analyst_id?: string | null;
    processing_mode?: string | null;

    transcription_engine?: string | null;
    save_in_conversation?: boolean;
    save_output?: boolean;
    save_output_path?: string;

    [key: string]: unknown;
  }

  export type UrlHeaderRow = {
    id: string;
    key: string;
    value: string;
    keyType: "known" | "custom";
  };
