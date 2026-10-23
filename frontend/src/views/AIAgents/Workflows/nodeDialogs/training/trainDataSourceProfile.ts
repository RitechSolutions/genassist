import type { ProfileDataRequest } from '@/services/mlModels';

export interface TrainDataSourceProfileValues {
  sourceType: 'datasource' | 'csv';
  dataSourceId?: string | null;
  query?: string | null;
  csvFileName?: string | null;
  csvFilePath?: string | null;
  csvFileId?: string | null;
  csvFileUrl?: string | null;
  sheetName?: string | null;
}

// File types Train Data Source can read (backend: training_file_readers.py).
export const TRAINING_FILE_TYPES = ['.csv', '.parquet', '.xlsx', '.xlsm', '.json', '.jsonl', '.ndjson'];

export function isSupportedTrainingFile(fileName?: string | null): boolean {
  const name = fileName?.toLowerCase() ?? '';
  return TRAINING_FILE_TYPES.some((type) => name.endsWith(type));
}

export function isExcelFile(fileName?: string | null): boolean {
  return /\.xls[xm]$/i.test(fileName ?? '');
}

export interface ProfileDataAvailability {
  visible: boolean;
  enabled: boolean;
  reason?: string;
}

const WORKFLOW_VARIABLE_PATTERN = /{{[^\s{}]+}}/;

export const WORKFLOW_VARIABLE_PROFILE_REASON =
  'Replace workflow variables like {{chat.input}} with sample values to profile.';

export function getProfileDataAvailability(values: TrainDataSourceProfileValues): ProfileDataAvailability {
  if (values.sourceType === 'datasource') {
    const query = values.query?.trim();
    if (!values.dataSourceId || !query) {
      return { visible: false, enabled: false };
    }
    if (WORKFLOW_VARIABLE_PATTERN.test(query)) {
      return {
        visible: true,
        enabled: false,
        reason: WORKFLOW_VARIABLE_PROFILE_REASON,
      };
    }
    return { visible: true, enabled: true };
  }

  const hasFile = Boolean(values.csvFileId || values.csvFilePath || values.csvFileUrl);
  const available = hasFile && isSupportedTrainingFile(values.csvFileName);
  return { visible: available, enabled: available };
}

export function buildProfileDataRequest(values: TrainDataSourceProfileValues): ProfileDataRequest | null {
  if (!getProfileDataAvailability(values).enabled) return null;

  if (values.sourceType === 'datasource') {
    return {
      source_type: 'datasource',
      data_source_id: values.dataSourceId!,
      query: values.query!.trim(),
    };
  }

  return {
    source_type: 'csv',
    file_id: values.csvFileId || undefined,
    file_url: values.csvFilePath || values.csvFileUrl || undefined,
    file_name: values.csvFileName || undefined,
    sheet_name: (isExcelFile(values.csvFileName) && values.sheetName) || undefined,
  };
}
