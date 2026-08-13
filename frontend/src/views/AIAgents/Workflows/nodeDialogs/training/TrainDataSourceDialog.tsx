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
import { Save } from "lucide-react";
import { NodeConfigPanel } from "../../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "../base";
import { DraggableTextArea } from "../../components/custom/DraggableTextArea";
import { FileUploader } from "@/components/FileUploader";
import { useNodeDialogState } from "../useNodeDialogState";

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
  const [availableDataSources, setAvailableDataSources] = useState<
    DataSource[]
  >([]);
  const { toast } = useToast();

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
          description: "Please upload a CSV file",
          variant: "destructive",
        });
        return;
      }
    }

    onUpdate(merged);
    onClose();
  };

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
              <SelectItem value="csv">CSV Upload</SelectItem>
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            Select a TimeDB, Snowflake, or other database source, or upload a
            CSV file
          </p>
        </div>

        {/* Data Source Configuration */}
        {values.sourceType === "datasource" && (
          <div className="space-y-2">
            <Label htmlFor="query">Query *</Label>
            <DraggableTextArea
              id="query"
              value={values.query ?? ""}
              onChange={(e) => setField("query", e.target.value || null)}
              placeholder="SELECT * FROM training_data WHERE ..."
              className="w-full min-h-[120px] font-mono text-sm"
            />
            <p className="text-xs text-muted-foreground">
              SQL query to fetch training data. Use variables from previous
              nodes if needed.
            </p>
          </div>
        )}

        {/* CSV Upload Configuration */}
        {values.sourceType === "csv" && (
          <FileUploader
            label="Training File"
            acceptedFileTypes={[".csv"]}
            initialServerFilePath={values.csvFilePath ?? ""}
            initialServerFileUrl={values.csvFileUrl ?? ""}
            initialOriginalFileName={values.csvFileName ?? ""}
            onUploadingChange={setIsCsvUploading}
            onUploadComplete={(result) => {
              setValues((v) => ({
                ...v,
                csvFileName: result.original_filename,
                csvFilePath: result.file_path,
                csvFileId: result.file_id,
                csvFileUrl: result.file_url,
              }));
            }}
            onRemove={() => {
              setValues((v) => ({
                ...v,
                csvFileName: null,
                csvFilePath: null,
                csvFileId: null,
                csvFileUrl: null,
              }));
            }}
            placeholder="Select a CSV file to upload"
          />
        )}
      </div>
    </NodeConfigPanel>
  );
};
