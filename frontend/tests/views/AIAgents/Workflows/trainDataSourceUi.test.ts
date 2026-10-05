import { describe, expect, it } from 'vitest';

import type { DataSource } from '@/interfaces/dataSource.interface';
import {
  getTrainDataSourceSelection,
  isTrainingDatabaseSource,
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

describe('Train Data Source UI', () => {
  it('keeps a new database node in database mode before a source is selected', () => {
    expect(
      getTrainDataSourceSelection({
        sourceType: 'datasource',
        dataSourceId: '',
      }),
    ).toEqual({
      sourceType: 'datasource',
      selectedSource: '',
    });
  });

  it('selects the saved database or uploaded-file mode', () => {
    expect(
      getTrainDataSourceSelection({
        sourceType: 'datasource',
        dataSourceId: 'database-1',
      }),
    ).toEqual({
      sourceType: 'datasource',
      selectedSource: 'database-1',
    });
    expect(getTrainDataSourceSelection({ sourceType: 'csv' })).toEqual({
      sourceType: 'csv',
      selectedSource: 'csv',
    });
  });

  it('keeps older uploaded-file nodes working when sourceType is absent', () => {
    expect(
      getTrainDataSourceSelection({ csvFilePath: '/data/training.csv' }),
    ).toEqual({
      sourceType: 'csv',
      selectedSource: 'csv',
    });
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
});
