import { describe, expect, it } from 'vitest';

import type { DataSource } from '@/interfaces/dataSource.interface';
import {
  applyTrainDataSourceType,
  getTrainDataSourceSelection,
  getTrainDataSourceShape,
  getTrainDataSourceSummary,
  getTrainDataSourceVisibleFields,
  hasTrainDataSourceConfigurationChanged,
  isTrainingDatabaseSource,
  TRAIN_DATA_SOURCE_TYPE_OPTIONS,
  TRAINING_FILE_EXTENSIONS,
  type TrainDataSourceDialogValues,
  validateTrainDataSource,
} from '@/views/AIAgents/Workflows/utils/trainDataSource';

function dataSource(sourceType: string): DataSource {
  return {
    id: sourceType,
    name: sourceType,
    source_type: sourceType,
    connection_data: {},
    is_active: 1,
  };
}

function dialogValues(
  overrides: Partial<TrainDataSourceDialogValues>,
): TrainDataSourceDialogValues {
  return {
    name: 'Train Data Source',
    sourceType: '',
    dataSourceId: null,
    query: null,
    csvFileName: null,
    csvFilePath: null,
    csvFileId: null,
    csvFileUrl: null,
    analysisResult: null,
    ...overrides,
  };
}

describe('Train Data Source UI', () => {
  it('leaves a new node with no source type selected', () => {
    expect(
      getTrainDataSourceSelection({
        sourceType: '',
        dataSourceId: '',
        query: '',
        csvFileName: '',
        csvFilePath: '',
      }),
    ).toEqual({ sourceType: '' });
    expect(getTrainDataSourceVisibleFields('')).toEqual({
      dataSource: false,
      query: false,
      trainingFile: false,
    });
  });

  it('offers Database and Uploaded File as the source types', () => {
    expect(TRAIN_DATA_SOURCE_TYPE_OPTIONS).toEqual([
      { value: 'datasource', label: 'Database' },
      { value: 'csv', label: 'Uploaded File' },
    ]);
  });

  it('shows the data source and query only for Database', () => {
    expect(getTrainDataSourceVisibleFields('datasource')).toEqual({
      dataSource: true,
      query: true,
      trainingFile: false,
    });
  });

  it('shows the training file only for Uploaded File', () => {
    expect(getTrainDataSourceVisibleFields('csv')).toEqual({
      dataSource: false,
      query: false,
      trainingFile: true,
    });
  });

  it('opens previously saved database and uploaded-file nodes as saved', () => {
    expect(
      getTrainDataSourceSelection({
        sourceType: 'datasource',
        dataSourceId: 'database-1',
      }),
    ).toEqual({ sourceType: 'datasource' });
    expect(
      getTrainDataSourceSelection({ sourceType: 'datasource', dataSourceId: '' }),
    ).toEqual({ sourceType: 'datasource' });
    expect(
      getTrainDataSourceSelection({ sourceType: 'csv', csvFileId: 'file-1' }),
    ).toEqual({ sourceType: 'csv' });
  });

  it('keeps older nodes working when sourceType is absent', () => {
    expect(
      getTrainDataSourceSelection({ csvFilePath: '/data/training.csv' }),
    ).toEqual({ sourceType: 'csv' });
    expect(getTrainDataSourceSelection({ csvFileId: 'file-1' })).toEqual({
      sourceType: 'csv',
    });
    expect(getTrainDataSourceSelection({ dataSourceId: 'database-1' })).toEqual({
      sourceType: 'datasource',
    });
  });

  it('reports one specific validation message at a time', () => {
    const empty = dialogValues({});
    expect(validateTrainDataSource(empty)).toBe('Select a source type.');
    expect(
      validateTrainDataSource({ ...empty, sourceType: 'datasource' }),
    ).toBe('Select a data source.');
    expect(
      validateTrainDataSource({
        ...empty,
        sourceType: 'datasource',
        dataSourceId: 'database-1',
        query: '   ',
      }),
    ).toBe('Provide a query.');
    expect(validateTrainDataSource({ ...empty, sourceType: 'csv' })).toBe(
      'Upload a training file.',
    );
  });

  it('accepts a complete database or uploaded-file configuration', () => {
    expect(
      validateTrainDataSource(
        dialogValues({
          sourceType: 'datasource',
          dataSourceId: 'database-1',
          query: 'SELECT 1',
        }),
      ),
    ).toBeNull();
    // S3-backed uploads have an ID and URL but no server path.
    expect(
      validateTrainDataSource(
        dialogValues({ sourceType: 'csv', csvFileId: 'file-1' }),
      ),
    ).toBeNull();
  });

  it('requires an uploaded file that workflow execution can resolve', () => {
    expect(
      validateTrainDataSource(
        dialogValues({
          sourceType: 'csv',
          csvFileName: 'training.csv',
          csvFileUrl: 'https://example.test/files/training.csv',
        }),
      ),
    ).toBe('Upload a training file.');
    expect(
      validateTrainDataSource(
        dialogValues({
          sourceType: 'csv',
          csvFilePath: '/data/training.csv',
        }),
      ),
    ).toBeNull();
  });

  it('clears the database selection and query when switching to Uploaded File', () => {
    const database = dialogValues({
      sourceType: 'datasource',
      dataSourceId: 'database-1',
      query: 'SELECT 1',
    });

    expect(applyTrainDataSourceType(database, 'csv')).toEqual({
      ...database,
      sourceType: 'csv',
      dataSourceId: null,
      query: null,
    });
  });

  it('clears the uploaded file and its analysis when switching to Database', () => {
    const uploaded = dialogValues({
      sourceType: 'csv',
      csvFileName: 'training.csv',
      csvFilePath: '/data/training.csv',
      csvFileId: 'file-1',
      csvFileUrl: 'https://example.test/files/file-1',
      analysisResult: {
        row_count: 2,
        column_count: 1,
        column_names: ['a'],
        sample_data: [],
        columns_info: [],
      },
    });

    expect(applyTrainDataSourceType(uploaded, 'datasource')).toEqual({
      ...uploaded,
      sourceType: 'datasource',
      csvFileName: null,
      csvFilePath: null,
      csvFileId: null,
      csvFileUrl: null,
      analysisResult: null,
    });
  });

  it('keeps every value when the same source type is selected again', () => {
    const database = dialogValues({
      sourceType: 'datasource',
      dataSourceId: 'database-1',
      query: 'SELECT 1',
    });

    expect(applyTrainDataSourceType(database, 'datasource')).toBe(database);
  });

  it('detects changes that invalidate a previous test result', () => {
    const current = dialogValues({
      sourceType: 'datasource',
      dataSourceId: 'database-1',
      query: 'SELECT 1',
    });

    expect(
      hasTrainDataSourceConfigurationChanged(current, {
        ...current,
        query: 'SELECT 2',
      }),
    ).toBe(true);
    expect(
      hasTrainDataSourceConfigurationChanged(current, {
        ...current,
        name: 'Renamed Train Data Source',
      }),
    ).toBe(false);
  });

  it('treats an inferred legacy source type as unchanged', () => {
    expect(
      hasTrainDataSourceConfigurationChanged(
        { csvFilePath: '/data/training.csv' },
        { sourceType: 'csv', csvFilePath: '/data/training.csv' },
      ),
    ).toBe(false);
  });

  it.each([
    'database',
    'mssql',
    'mysql',
    'postgresql',
    'snowflake',
    'sql',
    'sqlite',
    'timedb',
    'timescaledb',
  ])('includes the supported %s source type', (sourceType) => {
    expect(isTrainingDatabaseSource(dataSource(sourceType))).toBe(true);
  });

  it('excludes non-database integrations and misleading partial matches', () => {
    expect(isTrainingDatabaseSource(dataSource('gmail'))).toBe(false);
    expect(isTrainingDatabaseSource(dataSource('nosql'))).toBe(false);
  });

  it('offers CSV as the supported uploaded training-file format', () => {
    expect(TRAINING_FILE_EXTENSIONS).toEqual(['.csv']);
  });

  it('builds a clear uploaded-file summary without showing a query', () => {
    expect(
      getTrainDataSourceSummary({
        sourceType: 'csv',
        csvFileName: 'training.parquet',
        query: 'SELECT * FROM stale_query',
      }),
    ).toEqual({
      sourceTypeLabel: 'Uploaded File',
      sourceFieldLabel: 'Data Source',
      sourceLabel: 'training.parquet',
    });
  });

  it('shows a node with no source type as not configured', () => {
    expect(getTrainDataSourceSummary({ sourceType: '' })).toEqual({
      sourceTypeLabel: 'Not configured',
      sourceFieldLabel: 'Data Source',
    });
  });

  it('shows the saved source type before a data source or file is chosen', () => {
    expect(getTrainDataSourceSummary({ sourceType: 'datasource' })).toEqual({
      sourceTypeLabel: 'Database',
      sourceFieldLabel: 'Data Source',
    });
    expect(getTrainDataSourceSummary({ sourceType: 'csv' })).toEqual({
      sourceTypeLabel: 'Uploaded File',
      sourceFieldLabel: 'Data Source',
      sourceLabel: '',
    });
  });

  it('builds a compact database summary without showing the query', () => {
    expect(
      getTrainDataSourceSummary(
        {
          sourceType: 'datasource',
          dataSourceId: 'database-1',
          query: 'SELECT * FROM training_data',
        },
        { name: 'Warehouse' },
      ),
    ).toEqual({
      sourceTypeLabel: 'Database',
      sourceFieldLabel: 'Data Source',
      sourceLabel: 'Warehouse',
    });
  });

  it('shows the uploaded-file shape after analysis', () => {
    expect(
      getTrainDataSourceShape({
        sourceType: 'csv',
        analysisResult: {
          row_count: 2_500,
          column_count: 8,
          column_names: [],
          sample_data: [],
          columns_info: [],
        },
      }),
    ).toBe('2,500 rows × 8 columns');
  });

  it('shows the database shape after a successful test', () => {
    expect(
      getTrainDataSourceShape(
        { sourceType: 'datasource', dataSourceId: 'database-1' },
        { metadata: { rowCount: 1, columns: ['sample_value'] } },
      ),
    ).toBe('1 row × 1 column');
  });
});
