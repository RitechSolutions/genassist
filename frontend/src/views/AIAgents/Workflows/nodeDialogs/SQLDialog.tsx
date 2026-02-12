import React, { useState, useEffect } from "react";
import { SQLNodeData, SQLMode } from "../types/nodes";
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
import { LLMProvider } from "@/interfaces/llmProvider.interface";
import { getAllDataSources } from "@/services/dataSources";
import { getAllLLMProviders } from "@/services/llmProviders";
import { useToast } from "@/components/use-toast";
import { Save } from "lucide-react";
import { NodeConfigDialog } from "../components/NodeConfigDialog";
import { BaseNodeDialogProps } from "./base";
import { DraggableTextArea } from "../components/custom/DraggableTextArea";
import { DraggableInput } from "../components/custom/DraggableInput";
import { LLMProviderDialog } from "@/views/LlmProviders/components/LLMProviderDialog";
import { DataSourceDialog } from "@/views/DataSources/components/DataSourceDialog";
import { CreateNewSelectItem } from "@/components/CreateNewSelectItem";

type SQLDialogProps = BaseNodeDialogProps<SQLNodeData, SQLNodeData>;

export const SQLDialog: React.FC<SQLDialogProps> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const [name, setName] = useState(data.name || "");
  const [dataSourceId, setDatasourceId] = useState(data.dataSourceId || "");
  const [mode, setMode] = useState<SQLMode | undefined>(undefined);
  const [sqlQuery, setSqlQuery] = useState("");
  const [providerId, setProviderId] = useState(data.providerId || "");
  const [systemPrompt, setSystemPrompt] = useState(data.systemPrompt || "");
  const [humanQuery, setHumanQuery] = useState("");
  const [parameters, setParameters] = useState<Record<string, string>>(
    data.parameters || {},
  );
  const [availableProviders, setAvailableProviders] = useState<LLMProvider[]>(
    [],
  );
  const [availableDataSources, setAvailableDataSources] = useState<
    DataSource[]
  >([]);
  const { toast } = useToast();
  const [isCreateProviderOpen, setIsCreateProviderOpen] = useState(false);
  const [isCreateDataSourceOpen, setIsCreateDataSourceOpen] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setName(data.name || "");
      setDatasourceId(data.dataSourceId || "");
      setMode(data.mode || undefined);
      setSqlQuery(data.sqlQuery || "");
      setProviderId(data.providerId || "");
      setSystemPrompt(data.systemPrompt || "");
      setHumanQuery(data.humanQuery || "");
      setParameters(data.parameters || {});

      loadProviders();
      loadDataSources();
    }
  }, [isOpen, data]);

  const loadProviders = async () => {
    try {
      const providers = await getAllLLMProviders();
      setAvailableProviders(providers.filter((p) => p.is_active === 1));
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to load LLM providers",
        variant: "destructive",
      });
    }
  };

  const loadDataSources = async () => {
    try {
      const dataSources = await getAllDataSources();
      // Filter for database-type data sources
      const dbDataSources = dataSources.filter(
        (ds) =>
          ds.source_type.toLowerCase().includes("sql") ||
          ds.source_type.toLowerCase().includes("database") ||
          ds.source_type.toLowerCase().includes("mysql") ||
          ds.source_type.toLowerCase().includes("postgres") ||
          ds.source_type.toLowerCase().includes("sqlite") ||
          ds.source_type.toLowerCase().includes("snowflake"),
      );
      setAvailableDataSources(dbDataSources);
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to load data sources",
        variant: "destructive",
      });
    }
  };

  const handleSave = () => {
    onUpdate({
      ...data,
      name,
      dataSourceId,
      mode,
      sqlQuery,
      providerId,
      systemPrompt,
      humanQuery,
      parameters,
    });
    onClose();
  };

  return (
    <>
      <NodeConfigDialog
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
          dataSourceId,
          mode,
          sqlQuery,
          providerId,
          systemPrompt,
          humanQuery,
          parameters,
        }}
      >
        <div className="space-y-4">
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

          <div className="space-y-2">
            <Label htmlFor="datasource">Data Source</Label>
            <Select
              value={dataSourceId || ""}
              onValueChange={(value) => {
                if (value === "__create__") {
                  setIsCreateDataSourceOpen(true);
                  return;
                }
                setDatasourceId(value);
              }}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select a data source" />
              </SelectTrigger>
              <SelectContent>
                {availableDataSources.map((dataSource) => (
                  <SelectItem key={dataSource.id} value={dataSource.id!}>
                    {dataSource.name} ({dataSource.source_type})
                  </SelectItem>
                ))}
                <CreateNewSelectItem />
              </SelectContent>
            </Select>
            <p className="text-xs text-gray-500">
              Select the database data source to query
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="mode">Mode</Label>
            <Select
              value={mode || ""}
              onValueChange={(value) => setMode(value as SQLMode)}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select mode" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="sqlQuery">Write SQL Manually</SelectItem>
                <SelectItem value="humanQuery">
                  Generate SQL from Text
                </SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-gray-500">
              Choose how you want to provide the query
            </p>
          </div>

          {mode === "sqlQuery" && (
            <div className="space-y-2">
              <Label htmlFor="sqlQuery">SQL Query</Label>
              <DraggableTextArea
                id="sqlQuery"
                value={sqlQuery}
                onChange={(e) => setSqlQuery(e.target.value)}
                placeholder="Enter or drag and drop your SQL query here"
                className="w-full min-h-[150px] font-mono text-sm"
              />
              <p className="text-xs text-gray-500">
                Enter the SQL query to execute. Use variables from previous
                nodes if needed.
              </p>
            </div>
          )}

          {mode === "humanQuery" && (
            <>
              <div className="space-y-2">
                <Label htmlFor="provider">LLM Provider</Label>
                <Select
                  value={providerId || ""}
                  onValueChange={(value) => {
                    if (value === "__create__") {
                      setIsCreateProviderOpen(true);
                      return;
                    }
                    setProviderId(value);
                  }}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select an LLM provider" />
                  </SelectTrigger>
                  <SelectContent>
                    {availableProviders.map((provider) => (
                      <SelectItem key={provider.id} value={provider.id!}>
                        {provider.name}
                      </SelectItem>
                    ))}
                    <CreateNewSelectItem />
                  </SelectContent>
                </Select>
                <p className="text-xs text-gray-500">
                  Select the LLM provider to generate SQL from your text
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="systemPrompt">System Prompt</Label>
                <DraggableTextArea
                  id="systemPrompt"
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  placeholder="Enter system prompt for the SQL generator"
                  className="w-full min-h-[100px] text-sm"
                />
                <p className="text-xs text-gray-500">
                  Optional system prompt to guide the SQL generation behavior
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="humanQuery">Query in Plain English</Label>
                <DraggableTextArea
                  id="humanQuery"
                  value={humanQuery}
                  onChange={(e) => setHumanQuery(e.target.value)}
                  placeholder="e.g., Show me all customers who made purchases last month"
                  className="w-full min-h-[100px] text-sm"
                />
                <p className="text-xs text-gray-500">
                  Describe what you want to query in plain English. AI will
                  convert it to SQL.
                </p>
              </div>
            </>
          )}

          {mode && (
            <div className="space-y-2">
              <Label htmlFor="parameters">Parameters</Label>
              <div className="space-y-2">
                {Object.entries(parameters).map(([key, value], index) => (
                  <div key={index} className="flex gap-2">
                    <DraggableInput
                      placeholder="Parameter name"
                      value={key}
                      onChange={(e) => {
                        const newParameters = { ...parameters };
                        delete newParameters[key];
                        newParameters[e.target.value] = value;
                        setParameters(newParameters);
                      }}
                      className="flex-1"
                    />
                    <DraggableInput
                      placeholder="Parameter value"
                      value={value}
                      onChange={(e) => {
                        setParameters({
                          ...parameters,
                          [key]: e.target.value,
                        });
                      }}
                      className="flex-1"
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        const newParameters = { ...parameters };
                        delete newParameters[key];
                        setParameters(newParameters);
                      }}
                    >
                      Remove
                    </Button>
                  </div>
                ))}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setParameters({
                      ...parameters,
                      "": "",
                    });
                  }}
                >
                  Add Parameter
                </Button>
              </div>
              <p className="text-xs text-gray-500">
                Optional parameters that can be used in the SQL query. These
                will be passed to the backend for processing.
              </p>
            </div>
          )}
        </div>
      </NodeConfigDialog>
      <LLMProviderDialog
        isOpen={isCreateProviderOpen}
        onOpenChange={setIsCreateProviderOpen}
        onProviderSaved={async (provider) => {
          await loadProviders();
          if (provider?.id) {
            setProviderId(provider.id);
          }
        }}
        mode="create"
      />
      <DataSourceDialog
        isOpen={isCreateDataSourceOpen}
        onOpenChange={setIsCreateDataSourceOpen}
        onDataSourceSaved={async (created) => {
          await loadDataSources();
          if (created?.id) {
            setDatasourceId(created.id);
          }
        }}
        mode="create"
      />
    </>
  );
};
