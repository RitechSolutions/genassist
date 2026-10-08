import type { DataSource } from '@/interfaces/dataSource.interface';
import type { TrainDataSourceNodeData } from '../types/nodes';

const TRAINING_DATABASE_SOURCE_TYPES = new Set([
  'database',
  'mssql',
  'mysql',
  'postgres',
  'postgresql',
  'snowflake',
  'sql',
  'sqlite',
  'timedb',
  'timescale',
  'timescaledb',
]);

export const TRAINING_FILE_EXTENSIONS = ['.csv'] as const;

type TrainDataSourceSelectionData = Partial<
  Pick<
    TrainDataSourceNodeData,
    | 'name'
    | 'sourceType'
    | 'dataSourceId'
    | 'csvFileName'
    | 'csvFilePath'
    | 'csvFileId'
    | 'csvFileUrl'
    | 'query'
    | 'analysisResult'
  >
>;

export type TrainDataSourceType = TrainDataSourceNodeData['sourceType'];

export const TRAIN_DATA_SOURCE_TYPE_OPTIONS = [
  { value: 'datasource', label: 'Database' },
  { value: 'csv', label: 'Uploaded File' },
] as const;

export interface TrainDataSourceSelection {
  sourceType: TrainDataSourceType;
}

// In-progress dialog values; null marks a field the user has cleared.
export interface TrainDataSourceDialogValues {
  name: string;
  sourceType: TrainDataSourceType;
  dataSourceId: string | null;
  query: string | null;
  csvFileName: string | null;
  csvFilePath: string | null;
  csvFileId: string | null;
  csvFileUrl: string | null;
  analysisResult: TrainDataSourceNodeData['analysisResult'] | null;
}

export interface TrainDataSourceSummary {
  sourceTypeLabel: 'Database' | 'Uploaded File' | 'Not configured';
  sourceFieldLabel: 'Data Source';
  sourceLabel?: string;
}

export function getTrainDataSourceSelection(
  data: TrainDataSourceSelectionData,
): TrainDataSourceSelection {
  if (data.sourceType === 'csv' || data.sourceType === 'datasource') {
    return { sourceType: data.sourceType };
  }

  // Older nodes may have no sourceType; infer it from what they configured.
  const hasLegacyFile = Boolean(
    data.csvFileName || data.csvFilePath || data.csvFileId || data.csvFileUrl,
  );
  if (hasLegacyFile) return { sourceType: 'csv' };
  if (data.dataSourceId) return { sourceType: 'datasource' };

  return { sourceType: '' };
}

export function getTrainDataSourceVisibleFields(sourceType: TrainDataSourceType) {
  return {
    dataSource: sourceType === 'datasource',
    query: sourceType === 'datasource',
    trainingFile: sourceType === 'csv',
  };
}

export function applyTrainDataSourceType(
  values: TrainDataSourceDialogValues,
  sourceType: TrainDataSourceType,
): TrainDataSourceDialogValues {
  if (sourceType === values.sourceType) return values;

  if (sourceType === 'csv') {
    return { ...values, sourceType, dataSourceId: null, query: null };
  }

  return {
    ...values,
    sourceType,
    csvFileName: null,
    csvFilePath: null,
    csvFileId: null,
    csvFileUrl: null,
    analysisResult: null,
  };
}

export function validateTrainDataSource(
  values: Pick<
    TrainDataSourceDialogValues,
    | 'sourceType'
    | 'dataSourceId'
    | 'query'
    | 'csvFileName'
    | 'csvFilePath'
    | 'csvFileId'
    | 'csvFileUrl'
  >,
): string | null {
  if (values.sourceType === 'datasource') {
    if (!values.dataSourceId) return 'Select a data source.';
    if (!values.query?.trim()) return 'Provide a query.';
    return null;
  }

  if (values.sourceType === 'csv') {
    // Workflow extraction can resolve a local path or a File Manager ID.
    // A display name or URL alone is not enough to retrieve the file safely.
    const hasFile = values.csvFilePath || values.csvFileId;
    return hasFile ? null : 'Upload a training file.';
  }

  return 'Select a source type.';
}

export function hasTrainDataSourceConfigurationChanged(
  current: TrainDataSourceSelectionData,
  next: TrainDataSourceSelectionData,
): boolean {
  if (
    getTrainDataSourceSelection(current).sourceType !==
    getTrainDataSourceSelection(next).sourceType
  ) {
    return true;
  }

  const fields: Array<keyof TrainDataSourceSelectionData> = [
    'dataSourceId',
    'query',
    'csvFileName',
    'csvFilePath',
    'csvFileId',
    'csvFileUrl',
  ];

  return fields.some((field) => (current[field] ?? '') !== (next[field] ?? ''));
}

export function isTrainingDatabaseSource(dataSource: DataSource): boolean {
  return TRAINING_DATABASE_SOURCE_TYPES.has(
    dataSource.source_type.trim().toLowerCase(),
  );
}

export function getTrainDataSourceSummary(
  data: TrainDataSourceSelectionData,
  selectedDataSource?: Pick<DataSource, 'name'>,
): TrainDataSourceSummary {
  const { sourceType } = getTrainDataSourceSelection(data);
  if (sourceType === 'csv') {
    return {
      sourceTypeLabel: 'Uploaded File',
      sourceFieldLabel: 'Data Source',
      sourceLabel:
        data.csvFileName ||
        (data.csvFilePath || data.csvFileId || data.csvFileUrl
          ? 'Uploaded file'
          : ''),
    };
  }

  if (sourceType !== 'datasource') {
    return {
      sourceTypeLabel: 'Not configured',
      sourceFieldLabel: 'Data Source',
    };
  }

  // The chosen source type is shown as soon as it is saved, even before a
  // data source is picked, so the card always reflects the saved selection.
  if (!data.dataSourceId) {
    return {
      sourceTypeLabel: 'Database',
      sourceFieldLabel: 'Data Source',
    };
  }

  return {
    sourceTypeLabel: 'Database',
    sourceFieldLabel: 'Data Source',
    sourceLabel: selectedDataSource
      ? selectedDataSource.name
      : 'Unavailable data source',
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function getTrainDataSourceShape(
  data: TrainDataSourceSelectionData,
  runtimeOutput?: Record<string, unknown>,
): string {
  let rowCount = data.analysisResult?.row_count;
  let columnCount = data.analysisResult?.column_count;

  const metadata = isRecord(runtimeOutput?.metadata)
    ? runtimeOutput.metadata
    : undefined;
  if (rowCount === undefined && typeof metadata?.rowCount === 'number') {
    rowCount = metadata.rowCount;
  }
  if (columnCount === undefined && Array.isArray(metadata?.columns)) {
    columnCount = metadata.columns.length;
  }

  if (rowCount === undefined || columnCount === undefined) return '';

  return `${rowCount.toLocaleString()} ${rowCount === 1 ? 'row' : 'rows'} × ${columnCount.toLocaleString()} ${columnCount === 1 ? 'column' : 'columns'}`;
}
