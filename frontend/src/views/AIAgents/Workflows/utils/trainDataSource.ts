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

type TrainDataSourceSelectionData = Partial<
  Pick<
    TrainDataSourceNodeData,
    | 'sourceType'
    | 'dataSourceId'
    | 'csvFileName'
    | 'csvFilePath'
    | 'csvFileId'
    | 'csvFileUrl'
  >
>;

export interface TrainDataSourceSelection {
  sourceType: 'datasource' | 'csv';
  selectedSource: string;
}

export function getTrainDataSourceSelection(
  data: TrainDataSourceSelectionData,
): TrainDataSourceSelection {
  const hasLegacyFile = Boolean(
    data.csvFileName || data.csvFilePath || data.csvFileId || data.csvFileUrl,
  );
  const sourceType =
    data.sourceType === 'csv' || (!data.sourceType && hasLegacyFile)
      ? 'csv'
      : 'datasource';

  return {
    sourceType,
    selectedSource:
      sourceType === 'csv' ? 'csv' : data.dataSourceId || '',
  };
}

export function isTrainingDatabaseSource(dataSource: DataSource): boolean {
  return TRAINING_DATABASE_SOURCE_TYPES.has(
    dataSource.source_type.trim().toLowerCase(),
  );
}
