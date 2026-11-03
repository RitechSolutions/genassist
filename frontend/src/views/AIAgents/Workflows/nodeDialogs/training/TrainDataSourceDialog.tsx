import React, { useEffect, useState } from 'react';
import { Button } from '@/components/button';
import { FileUploader } from '@/components/FileUploader';
import { Label } from '@/components/label';
import { RichInput } from '@/components/richInput';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/select';
import { useToast } from '@/components/use-toast';
import { formatBytes } from '@/helpers/formatters';
import { DataSource } from '@/interfaces/dataSource.interface';
import { getAllDataSources } from '@/services/dataSources';
import {
  analyzeTrainingFile,
  CSVAnalysisResult,
  getTrainingDataLimits,
  previewQuery,
  profileData,
  TrainingDataLimits,
} from '@/services/mlModels';
import { BarChart3, Eye, Save } from 'lucide-react';
import { NodeConfigPanel } from '../../components/NodeConfigPanel';
import { DraggableTextArea } from '../../components/custom/DraggableTextArea';
import { TrainDataSourceNodeData } from '../../types/nodes';
import {
  applyTrainDataSourceType,
  getTrainDataSourceSelection,
  getTrainDataSourceVisibleFields,
  isTrainingDatabaseSource,
  TRAIN_DATA_SOURCE_TYPE_OPTIONS,
  TrainDataSourceDialogValues,
  TrainDataSourceType,
  validateTrainDataSource,
} from '../../utils/trainDataSource';
import { BaseNodeDialogProps } from '../base';
import { useNodeDialogState } from '../useNodeDialogState';
import { CSVAnalysisDisplay } from './components/CSVAnalysisDisplay';
import {
  TRAINING_FILE_TYPES,
  buildProfileDataRequest,
  createLatestRequestTracker,
  getProfileDataAvailability,
  isExcelFile,
  isSupportedTrainingFile,
} from './trainDataSourceProfile';

type TrainDataSourceDialogProps = BaseNodeDialogProps<TrainDataSourceNodeData, TrainDataSourceNodeData>;

export const TrainDataSourceDialog: React.FC<TrainDataSourceDialogProps> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const { values, setField, setValues, merged } = useNodeDialogState(
    props,
    (): TrainDataSourceDialogValues => ({
      name: data.name || 'Train Data Source',
      sourceType: getTrainDataSourceSelection(data).sourceType,
      dataSourceId: data.dataSourceId ?? null,
      query: data.query ?? null,
      csvFileName: data.csvFileName ?? null,
      csvFilePath: data.csvFilePath ?? null,
      csvFileId: data.csvFileId ?? null,
      csvFileUrl: data.csvFileUrl ?? null,
      sheetName: data.sheetName ?? null,
      analysisResult: data.analysisResult ?? null,
    }),
    (v) => ({
      name: v.name,
      sourceType: v.sourceType,
      dataSourceId: v.dataSourceId ?? undefined,
      query: v.query ?? undefined,
      csvFileName: v.csvFileName ?? undefined,
      csvFilePath: v.csvFilePath ?? undefined,
      csvFileId: v.csvFileId ?? undefined,
      csvFileUrl: v.csvFileUrl ?? undefined,
      sheetName: v.sheetName ?? undefined,
      analysisResult: v.analysisResult ?? undefined,
    })
  );

  const [isFileUploading, setIsFileUploading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isPreviewingQuery, setIsPreviewingQuery] = useState(false);
  const [queryPreviewResult, setQueryPreviewResult] = useState<CSVAnalysisResult | null>(null);
  // Switching files or Excel sheets quickly can overlap previews; only the latest may land.
  const [previewRequests] = useState(createLatestRequestTracker);
  const [isProfiling, setIsProfiling] = useState(false);
  const [availableDataSources, setAvailableDataSources] = useState<DataSource[]>([]);
  const [trainingLimits, setTrainingLimits] = useState<TrainingDataLimits | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    if (!isOpen) {
      setQueryPreviewResult(null);
      setIsPreviewingQuery(false);
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    getTrainingDataLimits().then((limits) => {
      if (!cancelled) setTrainingLimits(limits);
    });
    return () => {
      cancelled = true;
    };
  }, [isOpen]);

  useEffect(() => {
    if (isOpen && values.sourceType === 'datasource') {
      const loadDataSources = async () => {
        try {
          const dataSources = await getAllDataSources();

          const trainingDataSources = dataSources.filter(isTrainingDatabaseSource);
          setAvailableDataSources(trainingDataSources);
        } catch (err) {
          toast({
            title: 'Unable to Load Data Sources',
            description: "We couldn't load the available database sources. Please try again.",
            variant: 'destructive',
          });
        }
      };

      loadDataSources();
    }
  }, [isOpen, values.sourceType, toast]);

  // Preview any supported file. Local uploads by path; uploads without one
  // (S3 and other non-local storage) by File Manager id.
  const handleAnalyzeFile = async (
    file: { fileId?: string | null; filePath?: string | null; fileName: string },
    sheetName?: string | null
  ) => {
    const requestId = previewRequests.start();
    if (!isSupportedTrainingFile(file.fileName)) {
      setIsAnalyzing(false);
      setField('analysisResult', null);
      return;
    }

    try {
      setIsAnalyzing(true);
      const result = await analyzeTrainingFile({
        file_id: file.filePath ? undefined : file.fileId || undefined,
        file_url: file.filePath || undefined,
        file_name: file.fileName,
        sheet_name: sheetName || undefined,
      });
      if (!previewRequests.isLatest(requestId)) return;
      setValues((v) => ({
        ...v,
        analysisResult: result,
        // Excel: remember the sheet that was previewed (the first by default).
        sheetName: result.sheet_name ?? v.sheetName,
      }));
    } catch (err) {
      if (!previewRequests.isLatest(requestId)) return;
      console.error(err);
      setField('analysisResult', null);
      toast({
        title: 'Unable to Generate Preview',
        description: err instanceof Error ? err.message : 'The file preview could not be generated. Please try again.',
        variant: 'destructive',
      });
    } finally {
      if (previewRequests.isLatest(requestId)) setIsAnalyzing(false);
    }
  };

  const handleProfileData = async () => {
    const request = buildProfileDataRequest(values);
    if (!request) return;

    try {
      setIsProfiling(true);
      if (request.source_type === 'datasource') {
        await profileData(request, 'query_profile.html');
      } else {
        const baseName = (values.csvFileName || 'data').replace(/\.[^./]+$/, '');
        await profileData(request, `${baseName}_profile.html`);
      }
    } catch (err) {
      console.error(err);
      toast({
        title: 'Unable to Generate Profile',
        description: err instanceof Error ? err.message : 'The data profile could not be generated. Please try again.',
        variant: 'destructive',
      });
    } finally {
      setIsProfiling(false);
    }
  };

  const handlePreviewQuery = async () => {
    const dataSourceId = values.dataSourceId;
    const query = values.query?.trim();
    if (!dataSourceId || !query) return;

    try {
      setIsPreviewingQuery(true);
      const result = await previewQuery({
        data_source_id: dataSourceId,
        query,
      });
      setQueryPreviewResult(result);
    } catch (err) {
      console.error(err);
      setQueryPreviewResult(null);
      toast({
        title: 'Unable to Generate Preview',
        description: err instanceof Error ? err.message : 'The query preview could not be generated. Please try again.',
        variant: 'destructive',
      });
    } finally {
      setIsPreviewingQuery(false);
    }
  };

  const handlePreviewData = () => {
    if (values.sourceType === 'datasource') {
      return handlePreviewQuery();
    }

    if ((values.csvFilePath || values.csvFileId) && values.csvFileName) {
      return handleAnalyzeFile(
        {
          fileId: values.csvFileId,
          filePath: values.csvFilePath,
          fileName: values.csvFileName,
        },
        values.sheetName
      );
    }
  };

  const handleSourceTypeChange = (value: string) => {
    // Switching type drops the other type's values so they are never saved.
    setQueryPreviewResult(null);
    setValues((v) => applyTrainDataSourceType(v, value as TrainDataSourceType));
  };

  const handleSave = async () => {
    const validationError = validateTrainDataSource(values);
    if (validationError) {
      toast({
        title: 'Complete Required Fields',
        description: validationError,
        variant: 'destructive',
      });
      return;
    }

    onUpdate(merged);
    onClose();
  };

  const visibleFields = getTrainDataSourceVisibleFields(values.sourceType);
  const profileAvailability = getProfileDataAvailability(values);
  const isPreviewingData = values.sourceType === 'datasource' ? isPreviewingQuery : isAnalyzing;
  const hasPreviewData =
    values.sourceType === 'datasource' ? Boolean(queryPreviewResult) : Boolean(values.analysisResult);

  return (
    <NodeConfigPanel
      isOpen={isOpen}
      onClose={onClose}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave} loading={isFileUploading} icon={<Save className="h-4 w-4" />}>
            Save Changes
          </Button>
        </>
      }
      {...props}
      data={merged}
    >
      <div className="space-y-4">
        {/* Node Name */}
        <div className="space-y-2">
          <Label htmlFor="name">Node Name</Label>
          <RichInput
            id="name"
            value={values.name}
            onChange={(e) => setField('name', e.target.value)}
            placeholder="Enter the name of this node"
            className="w-full"
          />
        </div>

        {/* Source Type */}
        <div className="space-y-2">
          <Label htmlFor="sourceType">Source Type *</Label>
          <Select value={values.sourceType} onValueChange={handleSourceTypeChange}>
            <SelectTrigger id="sourceType" className="w-full">
              <SelectValue placeholder="Select a source type" />
            </SelectTrigger>
            <SelectContent>
              {TRAIN_DATA_SOURCE_TYPE_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">Choose a database source or upload a training file.</p>
        </div>

        {/* Database Configuration */}
        {visibleFields.dataSource && (
          <div className="space-y-2">
            <Label htmlFor="dataSourceId">Data Source *</Label>
            <Select
              value={values.dataSourceId ?? ''}
              onValueChange={(value) => {
                setField('dataSourceId', value);
                setQueryPreviewResult(null);
              }}
            >
              <SelectTrigger id="dataSourceId" className="w-full">
                <SelectValue placeholder="Select a data source" />
              </SelectTrigger>
              <SelectContent>
                {availableDataSources.map((dataSource) => (
                  <SelectItem key={dataSource.id} value={dataSource.id!}>
                    {dataSource.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
        {visibleFields.query && (
          <div className="space-y-2">
            <Label htmlFor="query">Query *</Label>
            <DraggableTextArea
              id="query"
              size="code"
              value={values.query ?? ''}
              onChange={(e) => {
                setField('query', e.target.value || null);
                setQueryPreviewResult(null);
              }}
              placeholder="SELECT column_1, column_2 FROM table_name"
              className="w-full font-mono text-sm"
            />
            <p className="text-xs text-muted-foreground">
              {'Workflow variables, such as {{chat.input}}, can be used only '}
              where the query expects a value, for example in WHERE or LIMIT clauses. They cannot be used as table or
              column names.
            </p>
          </div>
        )}

        {/* Uploaded File Configuration */}
        {visibleFields.trainingFile && (
          <FileUploader
            label="Training File *"
            acceptedFileTypes={TRAINING_FILE_TYPES}
            initialServerFilePath={values.csvFilePath ?? ''}
            initialServerFileUrl={values.csvFileUrl ?? ''}
            initialOriginalFileName={values.csvFileName ?? ''}
            onUploadingChange={setIsFileUploading}
            uploadPurpose="training_data"
            maxFileSizeBytes={trainingLimits?.max_upload_bytes}
            maxFileSizeLabel={trainingLimits?.max_upload_label}
            onUploadComplete={(result) => {
              setValues((v) => ({
                ...v,
                csvFileName: result.original_filename,
                csvFilePath: result.file_path,
                csvFileId: result.file_id,
                csvFileUrl: result.file_url,
                sheetName: null,
                analysisResult: null,
              }));
              if (result.file_id || result.file_path) {
                handleAnalyzeFile({
                  fileId: result.file_id,
                  filePath: result.file_path,
                  fileName: result.original_filename,
                });
              }
            }}
            onRemove={() => {
              previewRequests.start(); // a preview still running is for the removed file
              setIsAnalyzing(false);
              setValues((v) => ({
                ...v,
                csvFileName: null,
                csvFilePath: null,
                csvFileId: null,
                csvFileUrl: null,
                sheetName: null,
                analysisResult: null,
              }));
            }}
            placeholder="Select a CSV, Parquet, Excel or JSON file to upload"
          />
        )}
        {visibleFields.trainingFile && (
          <p className="text-xs text-muted-foreground">
            Supported: {TRAINING_FILE_TYPES.join(', ')}. Excel reads one sheet; a .json file must be an array of objects
            {trainingLimits &&
              trainingLimits.json_max_bytes < trainingLimits.max_upload_bytes &&
              ` of up to ${formatBytes(trainingLimits.json_max_bytes)}`}{' '}
            (use .jsonl for large data).
          </p>
        )}
        {visibleFields.trainingFile &&
          isExcelFile(values.csvFileName) &&
          (values.analysisResult?.sheet_names?.length ?? 0) > 1 && (
            <div className="space-y-2">
              <Label htmlFor="sheet">Sheet</Label>
              <Select
                value={values.sheetName ?? values.analysisResult?.sheet_name ?? ''}
                onValueChange={(sheet) => {
                  setField('sheetName', sheet);
                  handleAnalyzeFile(
                    {
                      fileId: values.csvFileId,
                      filePath: values.csvFilePath,
                      fileName: values.csvFileName ?? '',
                    },
                    sheet
                  );
                }}
              >
                <SelectTrigger id="sheet" className="w-full">
                  <SelectValue placeholder="Select a sheet" />
                </SelectTrigger>
                <SelectContent>
                  {values.analysisResult!.sheet_names!.map((sheet) => (
                    <SelectItem key={sheet} value={sheet}>
                      {sheet}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
        {visibleFields.trainingFile && isAnalyzing && (
          <p className="text-xs text-muted-foreground">Generating data preview...</p>
        )}
        {visibleFields.trainingFile && values.analysisResult && (
          <CSVAnalysisDisplay analysisResult={values.analysisResult} />
        )}
        {values.sourceType === 'datasource' && isPreviewingQuery && (
          <p className="text-xs text-muted-foreground">Generating data preview...</p>
        )}
        {values.sourceType === 'datasource' && queryPreviewResult && (
          <CSVAnalysisDisplay analysisResult={queryPreviewResult} source="query" />
        )}
        {profileAvailability.visible && (
          <div className="space-y-1">
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handlePreviewData}
                loading={isPreviewingData}
                disabled={isPreviewingData || !profileAvailability.enabled}
                icon={<Eye className="h-4 w-4" />}
                className="w-fit"
              >
                {isPreviewingData ? 'Generating preview...' : hasPreviewData ? 'Refresh Preview' : 'Preview Data'}
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleProfileData}
                loading={isProfiling}
                disabled={isProfiling || !profileAvailability.enabled}
                icon={<BarChart3 className="h-4 w-4" />}
                className="w-fit"
              >
                {isProfiling ? 'Generating profile...' : 'Profile Data'}
              </Button>
            </div>
            {profileAvailability.reason && (
              <p className="text-xs text-muted-foreground">{profileAvailability.reason}</p>
            )}
          </div>
        )}
      </div>
    </NodeConfigPanel>
  );
};
