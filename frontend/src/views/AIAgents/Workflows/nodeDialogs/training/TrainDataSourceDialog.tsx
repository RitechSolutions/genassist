import React, { useState, useEffect } from 'react';
import { TrainDataSourceNodeData } from '../../types/nodes';
import { Button } from '@/components/button';
import { RichInput } from '@/components/richInput';
import { Label } from '@/components/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/select';
import { DataSource } from '@/interfaces/dataSource.interface';
import { getAllDataSources } from '@/services/dataSources';
import { useToast } from '@/components/use-toast';
import { Save, BarChart3, Eye } from 'lucide-react';
import { NodeConfigPanel } from '../../components/NodeConfigPanel';
import { BaseNodeDialogProps } from '../base';
import { DraggableTextArea } from '../../components/custom/DraggableTextArea';
import { FileUploader } from '@/components/FileUploader';
import { CSVAnalysisDisplay } from './components/CSVAnalysisDisplay';
import { analyzeCSV, CSVAnalysisResult, previewQuery, profileData } from '@/services/mlModels';
import { useNodeDialogState } from '../useNodeDialogState';
import { buildProfileDataRequest, getProfileDataAvailability } from './trainDataSourceProfile';
import {
  applyTrainDataSourceType,
  getTrainDataSourceSelection,
  getTrainDataSourceVisibleFields,
  isTrainingDatabaseSource,
  TRAIN_DATA_SOURCE_TYPE_OPTIONS,
  TRAINING_FILE_EXTENSIONS,
  TrainDataSourceDialogValues,
  TrainDataSourceType,
  validateTrainDataSource,
} from '../../utils/trainDataSource';

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
      analysisResult: v.analysisResult ?? undefined,
    })
  );

  const [isFileUploading, setIsFileUploading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isPreviewingQuery, setIsPreviewingQuery] = useState(false);
  const [queryPreviewResult, setQueryPreviewResult] = useState<CSVAnalysisResult | null>(null);
  const [isProfiling, setIsProfiling] = useState(false);
  const [availableDataSources, setAvailableDataSources] = useState<DataSource[]>([]);
  const { toast } = useToast();

  useEffect(() => {
    if (!isOpen) {
      setQueryPreviewResult(null);
      setIsPreviewingQuery(false);
    }
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

  const handleAnalyzeFile = async (fileUrl: string, fileName: string) => {
    // The backend preview endpoint only supports CSV files today.
    if (!fileName.toLowerCase().endsWith('.csv')) {
      setField('analysisResult', null);
      return;
    }

    try {
      setIsAnalyzing(true);
      const result = await analyzeCSV(fileUrl);
      setField('analysisResult', result);
    } catch (err) {
      console.error(err);
      setField('analysisResult', null);
      toast({
        title: 'Unable to Generate Preview',
        description: err instanceof Error ? err.message : 'The file preview could not be generated. Please try again.',
        variant: 'destructive',
      });
    } finally {
      setIsAnalyzing(false);
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

    const previewTarget = values.csvFilePath || values.csvFileUrl;
    if (previewTarget && values.csvFileName) {
      return handleAnalyzeFile(previewTarget, values.csvFileName);
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
  const hasPreviewData = values.sourceType === 'datasource' ? Boolean(queryPreviewResult) : Boolean(values.analysisResult);

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
            acceptedFileTypes={[...TRAINING_FILE_EXTENSIONS]}
            initialServerFilePath={values.csvFilePath ?? ''}
            initialServerFileUrl={values.csvFileUrl ?? ''}
            initialOriginalFileName={values.csvFileName ?? ''}
            onUploadingChange={setIsFileUploading}
            onUploadComplete={(result) => {
              setValues((v) => ({
                ...v,
                csvFileName: result.original_filename,
                csvFilePath: result.file_path,
                csvFileId: result.file_id,
                csvFileUrl: result.file_url,
                analysisResult: null,
              }));
            }}
            onRemove={() => {
              setValues((v) => ({
                ...v,
                csvFileName: null,
                csvFilePath: null,
                csvFileId: null,
                csvFileUrl: null,
                analysisResult: null,
              }));
            }}
            placeholder="Select a training file to upload"
          />
        )}
        {visibleFields.trainingFile && (
          <p className="text-xs text-muted-foreground">
            Upload a CSV file to use as training data. CSV files can be previewed and profiled.
          </p>
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
                {isPreviewingData
                  ? 'Generating preview...'
                  : hasPreviewData
                    ? 'Refresh Preview'
                    : 'Preview Data'}
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
