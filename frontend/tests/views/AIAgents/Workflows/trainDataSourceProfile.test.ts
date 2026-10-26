import { describe, expect, it } from 'vitest';

import {
  buildProfileDataRequest,
  createLatestRequestTracker,
  getProfileDataAvailability,
  isExcelFile,
  isSupportedTrainingFile,
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

  it.each(['training.parquet', 'training.xlsx', 'training.json', 'events.JSONL', 'rows.ndjson'])(
    'offers profiling for a %s upload',
    (csvFileName) => {
      const values = { sourceType: 'csv' as const, csvFileName, csvFileId: 'file-1' };
      expect(getProfileDataAvailability(values)).toEqual({ visible: true, enabled: true });
      expect(buildProfileDataRequest(values)).toMatchObject({ source_type: 'csv', file_id: 'file-1' });
    },
  );

  it('hides profiling for a file type that cannot be read', () => {
    const values = {
      sourceType: 'csv' as const,
      csvFileName: 'training.xls',
      csvFileId: 'file-1',
    };

    expect(getProfileDataAvailability(values)).toEqual({
      visible: false,
      enabled: false,
    });
    expect(buildProfileDataRequest(values)).toBeNull();
  });

  it('sends the chosen sheet for Excel uploads only', () => {
    expect(
      buildProfileDataRequest({
        sourceType: 'csv',
        csvFileName: 'book.xlsx',
        csvFileId: 'file-1',
        sheetName: 'Sales',
      }),
    ).toMatchObject({ sheet_name: 'Sales' });
    expect(
      buildProfileDataRequest({
        sourceType: 'csv',
        csvFileName: 'rows.csv',
        csvFileId: 'file-1',
        sheetName: 'Sales',
      }),
    ).toMatchObject({ sheet_name: undefined });
  });

  it('recognises supported training file types', () => {
    expect(isSupportedTrainingFile('A.PARQUET')).toBe(true);
    expect(isSupportedTrainingFile('notes.txt')).toBe(false);
    expect(isSupportedTrainingFile(null)).toBe(false);
    expect(isExcelFile('book.xlsm')).toBe(true);
    expect(isExcelFile('book.csv')).toBe(false);
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
});

describe('Train Data Source preview requests', () => {
  it('applies only the latest of overlapping previews (switching sheets quickly)', () => {
    const tracker = createLatestRequestTracker();
    const sheetA = tracker.start();
    const sheetB = tracker.start();

    // Sheet A's slower response arrives last: it must not overwrite sheet B.
    expect(tracker.isLatest(sheetB)).toBe(true);
    expect(tracker.isLatest(sheetA)).toBe(false);
  });

  it('drops a running preview once a newer request starts (e.g. the file was removed)', () => {
    const tracker = createLatestRequestTracker();
    const preview = tracker.start();
    tracker.start();

    expect(tracker.isLatest(preview)).toBe(false);
  });
});
