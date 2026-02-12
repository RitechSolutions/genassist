import React, { useState, useEffect } from "react";
import { TrainDataSourceNodeData } from "../../types/nodes";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
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

type TrainDataSourceDialogProps = BaseNodeDialogProps<
  TrainDataSourceNodeData,
  TrainDataSourceNodeData
>;

export const TrainDataSourceDialog: React.FC<TrainDataSourceDialogProps> = (
  props
) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const [name, setName] = useState(data.name || "Train Data Source");
  // sourceType is the single source of truth for which mode we're in
  const [sourceType, setSourceType] = useState<"datasource" | "csv">(() => {
    // Determine initial sourceType from existing data
    if (data.sourceType === "datasource" && data.dataSourceId) {
      return "datasource";
    }
    return "csv";
  });
  // selectedSource tracks what's selected in the dropdown (datasource ID or "csv")
  const [selectedSource, setSelectedSource] = useState<string>(() => {
    if (data.sourceType === "datasource" && data.dataSourceId) {
      return data.dataSourceId;
    }
    return "csv";
  });
  const [dataSourceId, setDataSourceId] = useState(data.dataSourceId ?? null);
  const [query, setQuery] = useState(data.query ?? null);
  const [csvFileName, setCsvFileName] = useState(data.csvFileName ?? null);
  const [csvFilePath, setCsvFilePath] = useState(data.csvFilePath ?? null);
  const [availableDataSources, setAvailableDataSources] = useState<
    DataSource[]
  >([]);
  const { toast } = useToast();

  useEffect(() => {
    if (isOpen) {
      setName(data.name || "Train Data Source");

      // Determine sourceType from data
      const currentSourceType: "datasource" | "csv" =
        data.sourceType === "datasource" && data.dataSourceId
          ? "datasource"
          : "csv";

      setSourceType(currentSourceType);

      // Set selectedSource based on sourceType
      const initialSelectedSource =
        currentSourceType === "datasource" && data.dataSourceId
          ? data.dataSourceId
          : "csv";

      setSelectedSource(initialSelectedSource);
      setDataSourceId(data.dataSourceId ?? null);
      setQuery(data.query ?? null);
      setCsvFileName(data.csvFileName ?? null);
      setCsvFilePath(data.csvFilePath ?? null);

      const loadDataSources = async () => {
        try {
          const dataSources = await getAllDataSources();
          console.log("Data sources:", dataSources);
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
      setSourceType("csv");
      setDataSourceId(null);
      // Clear query when switching to CSV mode
      setQuery(null);
    } else {
      // Otherwise, it's a datasource ID - switch to datasource mode
      setSourceType("datasource");
      setDataSourceId(value);
      // Preserve existing query if we're switching between datasources
      // Only clear if we were previously in CSV mode
      if (sourceType === "csv") {
        setQuery(null);
      }
      // If query is already set and we're switching datasources, keep it
    }
  };

  const handleSave = async () => {
    // Validate based on source type
    if (sourceType === "datasource") {
      if (!dataSourceId || !query || !query.trim()) {
        toast({
          title: "Validation Error",
          description: "Please select a data source and provide a query",
          variant: "destructive",
        });
        return;
      }
    } else if (sourceType === "csv") {
      if (!csvFileName && !csvFilePath) {
        toast({
          title: "Validation Error",
          description: "Please upload a CSV file",
          variant: "destructive",
        });
        return;
      }
    }

    onUpdate({
      ...data,
      name,
      sourceType,
      dataSourceId: dataSourceId ?? undefined,
      query: query ?? undefined,
      csvFileName: csvFileName ?? undefined,
      csvFilePath: csvFilePath ?? undefined,
    });
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
          <Button onClick={handleSave}>
            <Save className="h-4 w-4 mr-2" />
            Save Changes
          </Button>
        </>
      }
      {...props}
      data={{
        ...data,
        name,
        sourceType,
        dataSourceId,
        query,
        csvFileName,
      }}
    >
      <div className="space-y-4">
        {/* Node Name */}
        <div className="space-y-2">
          <Label htmlFor="name">Node Name</Label>
          <Input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
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
          <p className="text-xs text-gray-500">
            Select a TimeDB, Snowflake, or other database source, or upload a
            CSV file
          </p>
        </div>

        {/* Data Source Configuration */}
        {sourceType === "datasource" && (
          <div className="space-y-2">
            <Label htmlFor="query">Query *</Label>
            <DraggableTextArea
              id="query"
              value={query ?? ""}
              onChange={(e) => setQuery(e.target.value || null)}
              placeholder="SELECT * FROM training_data WHERE ..."
              className="w-full min-h-[120px] font-mono text-sm"
            />
            <p className="text-xs text-gray-500">
              SQL query to fetch training data. Use variables from previous
              nodes if needed.
            </p>
          </div>
        )}

        {/* CSV Upload Configuration */}
        {sourceType === "csv" && (
          <FileUploader
            label="Training File"
            acceptedFileTypes={[".csv"]}
            initialServerFilePath={csvFilePath ?? ""}
            initialOriginalFileName={csvFileName ?? ""}
            onUploadComplete={(result) => {
              setCsvFileName(result.original_filename);
              setCsvFilePath(result.file_path);
            }}
            onRemove={() => {
              setCsvFileName(null);
              setCsvFilePath(null);
            }}
            placeholder="Select a CSV file to upload"
          />
        )}
      </div>
    </NodeConfigPanel>
  );
};
