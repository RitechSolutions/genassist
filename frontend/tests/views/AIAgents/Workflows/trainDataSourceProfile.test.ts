import { describe, expect, it } from 'vitest';

import {
  buildProfileDataRequest,
  getProfileDataAvailability,
  WORKFLOW_VARIABLE_PROFILE_REASON,
} from '@/views/AIAgents/Workflows/nodeDialogs/training/trainDataSourceProfile';

describe('Train Data Source profiling', () => {
  it('builds a SQL request and trims the query', () => {
    const values = {
      sourceType: 'datasource' as const,
      dataSourceId: 'datasource-1',
      query: '  SELECT * FROM training_data  ',
    };

    expect(getProfileDataAvailability(values)).toEqual({
      visible: true,
      enabled: true,
    });
    expect(buildProfileDataRequest(values)).toEqual({
      source_type: 'datasource',
      data_source_id: 'datasource-1',
      query: 'SELECT * FROM training_data',
    });
  });

  it('builds an S3 CSV request with the File Manager ID', () => {
    const values = {
      sourceType: 'csv' as const,
      csvFileName: 'training.csv',
      csvFileId: 'file-1',
      csvFileUrl: 'https://example.test/file-manager/files/file-1/source',
    };

    expect(buildProfileDataRequest(values)).toEqual({
      source_type: 'csv',
      file_id: 'file-1',
      file_url: 'https://example.test/file-manager/files/file-1/source',
      file_name: 'training.csv',
    });
  });

  it('keeps profiling available for older CSV data with only a local path', () => {
    const values = {
      sourceType: 'csv' as const,
      csvFileName: 'training.csv',
      csvFilePath: '/data/training.csv',
    };

    expect(getProfileDataAvailability(values).enabled).toBe(true);
    expect(buildProfileDataRequest(values)).toEqual({
      source_type: 'csv',
      file_id: undefined,
      file_url: '/data/training.csv',
      file_name: 'training.csv',
    });
  });

  it('hides profiling for a non-CSV file', () => {
    const values = {
      sourceType: 'csv' as const,
      csvFileName: 'training.xlsx',
      csvFileId: 'file-1',
    };

    expect(getProfileDataAvailability(values)).toEqual({
      visible: false,
      enabled: false,
    });
    expect(buildProfileDataRequest(values)).toBeNull();
  });

  it('hides profiling for a blank query', () => {
    expect(
      getProfileDataAvailability({
        sourceType: 'datasource',
        dataSourceId: 'datasource-1',
        query: '   ',
      })
    ).toEqual({ visible: false, enabled: false });
  });

  it('hides profiling when no data source is selected', () => {
    expect(
      getProfileDataAvailability({
        sourceType: 'datasource',
        query: 'SELECT 1',
      })
    ).toEqual({ visible: false, enabled: false });
  });

  it('disables profiling and explains unresolved workflow variables', () => {
    const values = {
      sourceType: 'datasource' as const,
      dataSourceId: 'datasource-1',
      query: 'SELECT * FROM training_data WHERE id = {{chat.input}}',
    };

    expect(getProfileDataAvailability(values)).toEqual({
      visible: true,
      enabled: false,
      reason: WORKFLOW_VARIABLE_PROFILE_REASON,
    });
    expect(buildProfileDataRequest(values)).toBeNull();
  });

  it('offers no profile before a source type is selected', () => {
    const values = { sourceType: '' as const, csvFileName: 'stale.csv', csvFileId: 'file-1' };

    expect(getProfileDataAvailability(values)).toEqual({
      visible: false,
      enabled: false,
    });
    expect(buildProfileDataRequest(values)).toBeNull();
  });
});
