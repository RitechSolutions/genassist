import React, { useState, useEffect } from "react";
import { TrainDataSourceNodeData } from "../../types/nodes";
import { Button } from "@/components/button";
import { RichInput } from "@/components/richInput";
import { Label } from "@/components/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { DataSource } from "@/interfaces/dataSource.interface";
import { getAllDataSources } from "@/services/dataSources";
import { useToast } from "@/components/use-toast";
import { Save, BarChart3 } from "lucide-react";
import { NodeConfigPanel } from "../../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "../base";
import { DraggableTextArea } from "../../components/custom/DraggableTextArea";
import { FileUploader } from "@/components/FileUploader";
import { formatBytes } from "@/helpers/formatters";
import { CSVAnalysisDisplay } from "./components/CSVAnalysisDisplay";
import {
  analyzeTrainingFile,
  getTrainingDataLimits,
  profileData,
  TrainingDataLimits,
} from "@/services/mlModels";
import { useNodeDialogState } from "../useNodeDialogState";
import {
  TRAINING_FILE_TYPES,
  buildProfileDataRequest,
  createLatestRequestTracker,
  getProfileDataAvailability,
  isExcelFile,
  isSupportedTrainingFile,
} from "./trainDataSourceProfile";

type TrainDataSourceDialogProps = BaseNodeDialogProps<
  TrainDataSourceNodeData,
  TrainDataSourceNodeData
>;

export const TrainDataSourceDialog: React.FC<TrainDataSourceDialogProps> = (
  props
) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const { values, setField, setValues, merged } = useNodeDialogState(
    props,
    () => ({
      name: data.name || "Train Data Source",
      // Determine initial sourceType from existing data
      sourceType: (data.sourceType === "datasource" && data.dataSourceId
        ? "datasource"
        : "csv") as "datasource" | "csv",
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

  // selectedSource tracks what's selected in the dropdown (datasource ID or "csv")
  const [selectedSource, setSelectedSource] = useState<string>(() => {
    if (data.sourceType === "datasource" && data.dataSourceId) {
      return data.dataSourceId;
    }
    return "csv";
  });
  const [isCsvUploading, setIsCsvUploading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  // Switching sheets quickly overlaps previews; only the latest may land.
  const [previewRequests] = useState(createLatestRequestTracker);
  const [isProfiling, setIsProfiling] = useState(false);
  const [availableDataSources, setAvailableDataSources] = useState<
    DataSource[]
  >([]);
  const [trainingLimits, setTrainingLimits] = useState<TrainingDataLimits | null>(null);
  const { toast } = useToast();

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
    if (isOpen) {
      // Determine sourceType from data
      const currentSourceType: "datasource" | "csv" =
        data.sourceType === "datasource" && data.dataSourceId
          ? "datasource"
          : "csv";

      // Set selectedSource based on sourceType
      const initialSelectedSource =
        currentSourceType === "datasource" && data.dataSourceId
          ? data.dataSourceId
          : "csv";

      setSelectedSource(initialSelectedSource);

      const loadDataSources = async () => {
        try {
          const dataSources = await getAllDataSources();

          // Filter for timedb, snowflake, and other time-series or SQL databases
          const trainingDataSources = dataSources.filter((ds) =>
            ["snowflake", "database"].includes(ds.source_type.toLowerCase())
          );
          setAvailableDataSources(trainingDataSources);
        } catch (err) {
          toast({
            title: "Error",
            description: "Failed to load data sources",
            variant: "destructive",
          });
        }
      };

      loadDataSources();
    }
  }, [isOpen, data, toast]);

  // Preview any supported file. Local uploads by path; uploads without one
  // (S3 and other non-local storage) by File Manager id.
  const handleAnalyzeFile = async (
    file: { fileId?: string | null; filePath?: string | null; fileName: string },
    sheetName?: string | null,
  ) => {
    const requestId = previewRequests.start();
    if (!isSupportedTrainingFile(file.fileName)) {
      setIsAnalyzing(false);
      setField("analysisResult", null);
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
      toast({
        title: "Preview Failed",
        description:
          err instanceof Error ? err.message : "Failed to preview the file",
        variant: "destructive",
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
      if (request.source_type === "datasource") {
        await profileData(request, "query_profile.html");
      } else {
        const baseName = (values.csvFileName || "data").replace(
          /\.[^./]+$/,
          "",
        );
        await profileData(request, `${baseName}_profile.html`);
      }
    } catch (err) {
      console.error(err);
      toast({
        title: "Profiling Failed",
        description:
          err instanceof Error ? err.message : "Failed to generate data profile",
        variant: "destructive",
      });
    } finally {
      setIsProfiling(false);
    }
  };

  const handleSourceChange = (value: string) => {
    setSelectedSource(value);

    // If value is "csv", switch to CSV mode
    if (value === "csv") {
      setValues((v) => ({
        ...v,
        sourceType: "csv",
        dataSourceId: null,
        // Clear query when switching to CSV mode
        query: null,
      }));
    } else {
      // Otherwise, it's a datasource ID - switch to datasource mode
      setValues((v) => ({
        ...v,
        sourceType: "datasource",
        dataSourceId: value,
        // Preserve existing query if we're switching between datasources
        // Only clear if we were previously in CSV mode
        query: v.sourceType === "csv" ? null : v.query,
      }));
    }
  };

  const handleSave = async () => {
    // Validate based on source type
    if (values.sourceType === "datasource") {
      if (!values.dataSourceId || !values.query || !values.query.trim()) {
        toast({
          title: "Validation Error",
          description: "Please select a data source and provide a query",
          variant: "destructive",
        });
        return;
      }
    } else if (values.sourceType === "csv") {
      if (
        !values.csvFileName &&
        !values.csvFilePath &&
        !values.csvFileId &&
        !values.csvFileUrl
      ) {
        toast({
          title: "Validation Error",
          description: "Please upload a training file",
          variant: "destructive",
        });
        return;
      }
    }

    onUpdate(merged);
    onClose();
  };

  const profileAvailability = getProfileDataAvailability(values);

  return (
    <NodeConfigPanel
      isOpen={isOpen}
      onClose={onClose}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            loading={isCsvUploading}
            icon={<Save className="h-4 w-4" />}
          >
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
            onChange={(e) => setField("name", e.target.value)}
            placeholder="Enter the name of this node"
            className="w-full"
          />
        </div>

        {/* Data Source Selection */}
        <div className="space-y-2">
          <Label htmlFor="datasource">Select Data Source *</Label>
          <Select value={selectedSource} onValueChange={handleSourceChange}>
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select a data source" />
            </SelectTrigger>
            <SelectContent>
              {availableDataSources.map((dataSource) => (
                <SelectItem key={dataSource.id} value={dataSource.id!}>
                  {dataSource.name} ({dataSource.source_type})
                </SelectItem>
              ))}
              <SelectItem value="csv">File Upload</SelectItem>
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            Select a TimeDB, Snowflake, or other database source, or upload a
            file (CSV, Parquet, Excel, JSON or JSON Lines)
          </p>
        </div>

        {/* Data Source Configuration */}
        {values.sourceType === "datasource" && (
          <div className="space-y-2">
            <Label htmlFor="query">Query *</Label>
            <DraggableTextArea
              id="query"
              size="code"
              value={values.query ?? ""}
              onChange={(e) => setField("query", e.target.value || null)}
              placeholder="SELECT * FROM training_data WHERE ..."
              className="w-full font-mono text-sm"
            />
            <p className="text-xs text-muted-foreground">
              {"Variables like {{chat.input}} are sent to the database as values, "}
              so they are safe to use in WHERE and LIMIT. They cannot replace
              table or column names.
            </p>
          </div>
        )}

        {/* CSV Upload Configuration */}
        {values.sourceType === "csv" && (
          <FileUploader
            label="Training File"
            acceptedFileTypes={TRAINING_FILE_TYPES}
            initialServerFilePath={values.csvFilePath ?? ""}
            initialServerFileUrl={values.csvFileUrl ?? ""}
            initialOriginalFileName={values.csvFileName ?? ""}
            onUploadingChange={setIsCsvUploading}
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
        {values.sourceType === "csv" && (
          <p className="text-xs text-muted-foreground">
            Supported: {TRAINING_FILE_TYPES.join(", ")}. Excel reads one sheet;
            a .json file must be an array of objects
            {trainingLimits &&
              trainingLimits.json_max_bytes < trainingLimits.max_upload_bytes &&
              ` of up to ${formatBytes(trainingLimits.json_max_bytes)}`}{" "}
            (use .jsonl for large data).
          </p>
        )}
        {values.sourceType === "csv" &&
          isExcelFile(values.csvFileName) &&
          (values.analysisResult?.sheet_names?.length ?? 0) > 1 && (
            <div className="space-y-2">
              <Label htmlFor="sheet">Sheet</Label>
              <Select
                value={values.sheetName ?? values.analysisResult?.sheet_name ?? ""}
                onValueChange={(sheet) => {
                  setField("sheetName", sheet);
                  handleAnalyzeFile(
                    {
                      fileId: values.csvFileId,
                      filePath: values.csvFilePath,
                      fileName: values.csvFileName ?? "",
                    },
                    sheet,
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
        {values.sourceType === "csv" && isAnalyzing && (
          <p className="text-xs text-muted-foreground">
            Generating data preview...
          </p>
        )}
        {values.sourceType === "csv" && values.analysisResult && (
          <CSVAnalysisDisplay analysisResult={values.analysisResult} />
        )}
        {profileAvailability.visible && (
          <div className="space-y-1">
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
              {isProfiling ? "Generating profile..." : "Profile Data"}
            </Button>
            {profileAvailability.reason && (
              <p className="text-xs text-muted-foreground">
                {profileAvailability.reason}
              </p>
            )}
          </div>
        )}
      </div>
    </NodeConfigPanel>
  );
};
