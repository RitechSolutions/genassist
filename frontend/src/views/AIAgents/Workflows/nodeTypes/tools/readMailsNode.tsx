import React, { useState, useEffect } from "react";
import { NodeProps, useReactFlow } from "reactflow";
import { Input } from "@/components/input";
import { Textarea } from "@/components/textarea";
import { Button } from "@/components/button";
import { Label } from "@/components/label";
import { Checkbox } from "@/components/checkbox";
import { ScrollArea } from "@/components/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/select";
import { TestDialog } from "@/views/AIAgents/Workflows/components/TestDialog";
import { HandlersRenderer } from "@/views/AIAgents/Workflows/components/HandleTooltip";
import { ReadMailsNodeData } from "@/views/AIAgents/Workflows/types/nodes";
import { createSimpleSchema } from "@/views/AIAgents/Workflows/types/schemas";
import { useToast } from "@/components/use-toast";
import { Mail, Play, Save, Settings } from "lucide-react";
import { testReadMails } from "@/services/workflows";
import { getNodeColors } from "../../utils/nodeColors";
import { getAllDataSources } from "@/services/dataSources";
import { DataSource } from "@/interfaces/dataSource.interface";
import { useQuery } from "@tanstack/react-query";
import NodeHeader from "../nodeHeader";

interface SearchCriteria {
  from: string;
  to: string;
  subject: string;
  has_attachment: boolean;
  is_unread: boolean;
  label: string;
  newer_than: string;
  older_than: string;
  custom_query: string;
  max_results: number;
}

const ReadMailsNode: React.FC<NodeProps<ReadMailsNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const { getEdges } = useReactFlow();
  const [name, setName] = useState(data.name || "Read Mails");
  const [description, setDescription] = useState(
    data.description || "Search and read emails with filters"
  );
  
  const [searchCriteria, setSearchCriteria] = useState<SearchCriteria>({
    from: data.searchCriteria?.from || "",
    to: data.searchCriteria?.to || "",
    subject: data.searchCriteria?.subject || "",
    has_attachment: data.searchCriteria?.has_attachment || false,
    is_unread: data.searchCriteria?.is_unread || false,
    label: data.searchCriteria?.label || "",
    newer_than: data.searchCriteria?.newer_than || "",
    older_than: data.searchCriteria?.older_than || "",
    custom_query: data.searchCriteria?.custom_query || "",
    max_results: data.searchCriteria?.max_results || 10,
  });

  const [output, setOutput] = useState("");
  const [isTestDialogOpen, setIsTestDialogOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { toast } = useToast();

  const colors = getNodeColors("readMailsNode");

  // Query for Gmail data sources
  const { data: connectors = [] } = useQuery({
    queryKey: ["dataSources"],
    queryFn: getAllDataSources,
    select: (data: DataSource[]) =>
      data.filter((p) => p.is_active === 1 && p.source_type === "gmail"),
  });

  // Auto-select first available connector if none selected
  useEffect(() => {
    if (data.dataSourceId === undefined && connectors.length > 0) {
      if (data.updateNodeData) {
        data.updateNodeData(id, {
          ...data,
          dataSourceId: connectors[0].id,
        });
      }
    }
  }, [connectors, data.dataSourceId, id, data]);

  // Time period options
  const timePeriodOptions = [
    { value: "none", label: "None" },
    { value: "1h", label: "1 hour" },
    { value: "1d", label: "1 day" },
    { value: "2d", label: "2 days" },
    { value: "1w", label: "1 week" },
    { value: "2w", label: "2 weeks" },
    { value: "1m", label: "1 month" },
    { value: "3m", label: "3 months" },
    { value: "6m", label: "6 months" },
    { value: "1y", label: "1 year" }
  ];

  // Common Gmail labels
  const commonLabels = [
    "INBOX",
    "SENT",
    "DRAFT",
    "SPAM",
    "TRASH",
    "IMPORTANT",
    "STARRED",
    "CATEGORY_PERSONAL",
    "CATEGORY_SOCIAL",
    "CATEGORY_PROMOTIONS",
    "CATEGORY_UPDATES",
    "CATEGORY_FORUMS",
  ];

  // Save configuration whenever relevant state changes
  useEffect(() => {
    saveConfiguration();
  }, [name, description, searchCriteria]);

  const saveConfiguration = () => {
    // Create input schema - no dynamic inputs needed as all filters are configured
    const inputSchema = createSimpleSchema({});

    // Create output schema with emails array
    const outputSchema = createSimpleSchema({
      emails: {
        type: "array",
        description: "Array of email objects matching the search criteria",
        required: true,
      },
      total_count: {
        type: "number",
        description: "Total number of emails found",
        required: true,
      },
    });

    if (data.updateNodeData) {
      const updatedData: Partial<ReadMailsNodeData> = {
        name,
        description,
        searchCriteria,
        dataSourceId: data.dataSourceId,
        inputSchema,
        outputSchema,
      };

      data.updateNodeData(id, updatedData);
    }
  };

  const handleTest = async (inputs: Record<string, string>) => {
    setIsLoading(true);
    setError(null);
    try {
      const results = await testReadMails({
        ...searchCriteria,
        dataSourceId: data.dataSourceId,
      });
      setOutput(JSON.stringify(results, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setIsLoading(false);
    }
  };

  const updateSearchCriteria = (key: keyof SearchCriteria, value: any) => {
    setSearchCriteria(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const selectedConnectorName =
    connectors.find((c) => c.id === data.dataSourceId)?.name || "Not Selected";

  return (
    <>
      <div
        className={`border-2 rounded-md bg-white shadow-md w-[400px] ${
          selected ? "border-blue-500" : "border-gray-200"
        }`}
      >
        {/* Node header */}
        <NodeHeader
          iconName={"mail"}
          title={data.name || "Read Mails"}
          subtitle={"Search and read emails with filters"}
          color={colors.header}
          onTest={() => setIsTestDialogOpen(true)}
        />

        {/* Node content */}
        <div className="p-4">
          <ScrollArea className="h-96">
            <div className="space-y-4 pr-4">
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Input
                  id="description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Describe what this read mails node does"
                />
              </div>

              <div className="space-y-2">
                <Label>Gmail Data Source</Label>
                <Select
                  value={data.dataSourceId?.toString() || "none"}
                  onValueChange={(value) => {
                    if (data.updateNodeData && value !== "none") {
                      data.updateNodeData(id, {
                        ...data,
                        dataSourceId: parseInt(value),
                      });
                    }
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select Gmail account" />
                  </SelectTrigger>
                  <SelectContent>
                    {connectors.length === 0 ? (
                      <SelectItem value="none" disabled>
                        No Gmail accounts connected
                      </SelectItem>
                    ) : (
                      connectors.map((connector) => (
                        <SelectItem key={connector.id} value={connector.id.toString()}>
                          {connector.name}
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
                <div className="text-xs text-gray-500">
                  Selected: {selectedConnectorName}
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="from">From Email</Label>
                <Input
                  id="from"
                  value={searchCriteria.from}
                  onChange={(e) => updateSearchCriteria("from", e.target.value)}
                  placeholder="sender@example.com"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="to">To Email</Label>
                <Input
                  id="to"
                  value={searchCriteria.to}
                  onChange={(e) => updateSearchCriteria("to", e.target.value)}
                  placeholder="recipient@example.com"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="subject">Subject Contains</Label>
                <Input
                  id="subject"
                  value={searchCriteria.subject}
                  onChange={(e) => updateSearchCriteria("subject", e.target.value)}
                  placeholder="Enter subject text to search for"
                />
              </div>

              <div className="space-y-2">
                <Label>Gmail Label</Label>
                <Select
                  value={searchCriteria.label || "none"}
                  onValueChange={(value) => updateSearchCriteria("label", value === "none" ? "" : value)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select a label (optional)" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">None</SelectItem>
                    {commonLabels.map((label) => (
                      <SelectItem key={label} value={label}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Newer Than</Label>
                  <Select
                    value={searchCriteria.newer_than || "none"}
                    onValueChange={(value) => updateSearchCriteria("newer_than", value === "none" ? "" : value)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select time" />
                    </SelectTrigger>
                    <SelectContent>
                      {timePeriodOptions.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Older Than</Label>
                  <Select
                    value={searchCriteria.older_than || "none"}
                    onValueChange={(value) => updateSearchCriteria("older_than", value === "none" ? "" : value)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select time" />
                    </SelectTrigger>
                    <SelectContent>
                      {timePeriodOptions.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="max_results">Max Results</Label>
                <Input
                  id="max_results"
                  type="number"
                  value={searchCriteria.max_results}
                  onChange={(e) => updateSearchCriteria("max_results", parseInt(e.target.value) || 10)}
                  placeholder="10"
                  min="1"
                  max="500"
                />
              </div>

              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="has_attachment"
                    checked={searchCriteria.has_attachment}
                    onCheckedChange={(checked) => updateSearchCriteria("has_attachment", checked)}
                  />
                  <Label htmlFor="has_attachment" className="text-sm">
                    Has Attachment
                  </Label>
                </div>

                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="is_unread"
                    checked={searchCriteria.is_unread}
                    onCheckedChange={(checked) => updateSearchCriteria("is_unread", checked)}
                  />
                  <Label htmlFor="is_unread" className="text-sm">
                    Unread Only
                  </Label>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="custom_query">Custom Gmail Query</Label>
                <Textarea
                  id="custom_query"
                  value={searchCriteria.custom_query}
                  onChange={(e) => updateSearchCriteria("custom_query", e.target.value)}
                  placeholder="Enter raw Gmail search query (overrides other filters)"
                  className="h-16 font-mono text-xs"
                />
                <div className="text-xs text-gray-500">
                  Use Gmail search syntax. This will override other filters if specified.
                </div>
              </div>
            </div>
          </ScrollArea>
        </div>

        <HandlersRenderer id={id} data={data} />
      </div>

      <TestDialog
        isOpen={isTestDialogOpen}
        onClose={() => setIsTestDialogOpen(false)}
        title={`Test ${name}`}
        description="Test the email search with current filter settings"
        inputFields={[]} // No dynamic inputs needed
        onRun={handleTest}
        output={output}
        isLoading={isLoading}
        error={error}
      />
    </>
  );
};

export default ReadMailsNode;