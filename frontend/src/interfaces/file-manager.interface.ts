export interface UploadFileResponse {
  original_filename: string;
  file_path?: string;
  file_id?: string;
  file_type?: string;
  file_url?: string;
  filename?: string;
}

export interface FileManagerFileRecord {
  id: string;
  name: string;
  path: string;
  storage_path: string;
  storage_provider: string;
  original_filename?: string | null;
  size?: number | null;
  mime_type?: string | null;
  description?: string | null;
  file_extension?: string | null;
  created_at: string;
  updated_at: string;
  is_deleted: number;
}