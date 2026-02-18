import React, { useEffect, useState } from "react";
import { ReadMailsNodeData, SearchCriteria } from "../types/nodes";
import { DataSource } from "@/interfaces/dataSource.interface";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Checkbox } from "@/components/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Save } from "lucide-react";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { DraggableInput } from "../components/custom/DraggableInput";
import { DraggableTextArea } from "../components/custom/DraggableTextArea";
import { BaseNodeDialogProps } from "./base";
import { DataSourceDialog } from "@/views/DataSources/components/DataSourceDialog";
import { CreateNewSelectItem } from "@/components/CreateNewSelectItem";

interface ReadMailsDialogProps
  extends BaseNodeDialogProps<ReadMailsNodeData, ReadMailsNodeData> {
  connectors: DataSource[];
}

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
  { value: "1y", label: "1 year" },
];

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

const emptySearchCriteria: SearchCriteria = {
  from: "",
  to: "",
  subject: "",
  has_attachment: false,
  is_unread: false,
  label: "",
  newer_than: "",
  older_than: "",
  custom_query: "",
  max_results: 10,
};

export const ReadMailsDialog: React.FC<ReadMailsDialogProps> = (props) => {
  const { isOpen, onClose, data, onUpdate, connectors } = props;

  const [name, setName] = useState(data.name || "");
  const [dataSourceId, setDataSourceId] = useState(
    data.dataSourceId?.toString() || ""
  );
  const [searchCriteria, setSearchCriteria] = useState<SearchCriteria>(
    data.searchCriteria || emptySearchCriteria
  );
  const [isCreateDataSourceOpen, setIsCreateDataSourceOpen] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setName(data.name || "");
      setDataSourceId(data.dataSourceId?.toString() || "");
      setSearchCriteria(data.searchCriteria || emptySearchCriteria);
    }
  }, [isOpen, data]);

  const handleSave = () => {
    onUpdate({
      ...data,
      name,
      dataSourceId,
      searchCriteria,
    });
    onClose();
  };

  const updateSearchCriteriaField = (
    key: keyof SearchCriteria,
    value: string | boolean | number
  ) => {
    setSearchCriteria((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <>
      <NodeConfigPanel
        footer={
          <>
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button onClick={handleSave}>
              <Save className="h-4 w-4 mr-2" /> Save Changes
            </Button>
          </>
        }
        {...props}
        data={
          {
            ...data,
            name,
            dataSourceId,
            searchCriteria,
          } as ReadMailsNodeData
        }
      >
        <div className="space-y-2">
          <Label htmlFor="node-name">Node Name</Label>
          <Input
            id="node-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Enter the name of this node"
            className="w-full"
          />
        </div>

        <div className="space-y-2">
          <Label>Gmail Data Source</Label>
          <Select
            value={dataSourceId?.toString() || "none"}
            onValueChange={(v) => {
              if (v === "__create__") {
                setIsCreateDataSourceOpen(true);
                return;
              }
              setDataSourceId(v === "none" ? "" : v);
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
                connectors.map((c) => (
                  <SelectItem key={c.id} value={c.id.toString()}>
                    {c.name}
                  </SelectItem>
                ))
              )}
              <CreateNewSelectItem />
            </SelectContent>
          </Select>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="from">From Email</Label>
            <DraggableInput
              id="from"
              value={searchCriteria.from}
              onChange={(e) =>
                updateSearchCriteriaField("from", e.target.value)
              }
              placeholder="sender@example.com"
              className="w-full break-all"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="to">To Email</Label>
            <DraggableInput
              id="to"
              value={searchCriteria.to}
              onChange={(e) => updateSearchCriteriaField("to", e.target.value)}
              placeholder="recipient@example.com"
              className="w-full break-all"
            />
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="subject">Subject Contains</Label>
          <DraggableInput
            id="subject"
            value={searchCriteria.subject}
            onChange={(e) =>
              updateSearchCriteriaField("subject", e.target.value)
            }
            placeholder="Enter subject text to search for"
            className="w-full"
          />
        </div>

        <div className="space-y-2">
          <Label>Gmail Label</Label>
          <Select
            value={searchCriteria.label || "none"}
            onValueChange={(v) =>
              updateSearchCriteriaField("label", v === "none" ? "" : v)
            }
          >
            <SelectTrigger>
              <SelectValue placeholder="Select a label" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">None</SelectItem>
              {commonLabels.map((l) => (
                <SelectItem key={l} value={l}>
                  {l}
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
              onValueChange={(v) =>
                updateSearchCriteriaField("newer_than", v === "none" ? "" : v)
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Select time" />
              </SelectTrigger>
              <SelectContent>
                {timePeriodOptions.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Older Than</Label>
            <Select
              value={searchCriteria.older_than || "none"}
              onValueChange={(v) =>
                updateSearchCriteriaField("older_than", v === "none" ? "" : v)
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Select time" />
              </SelectTrigger>
              <SelectContent>
                {timePeriodOptions.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
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
            onChange={(e) =>
              updateSearchCriteriaField("max_results", parseInt(e.target.value))
            }
            min="1"
            max="500"
            placeholder="10"
            className="w-full"
          />
        </div>

        <div className="flex items-center space-x-6 pt-2">
          <div className="flex items-center space-x-2">
            <Checkbox
              id="has_attachment"
              checked={searchCriteria.has_attachment}
              onCheckedChange={(c) =>
                updateSearchCriteriaField("has_attachment", c)
              }
            />
            <Label htmlFor="has_attachment" className="cursor-pointer">
              Has Attachment
            </Label>
          </div>

          <div className="flex items-center space-x-2">
            <Checkbox
              id="is_unread"
              checked={searchCriteria.is_unread}
              onCheckedChange={(c) => updateSearchCriteriaField("is_unread", c)}
            />
            <Label htmlFor="is_unread" className="cursor-pointer">
              Unread Only
            </Label>
          </div>
        </div>

        <div className="space-y-2 pt-2">
          <Label htmlFor="custom_query">Custom Gmail Query</Label>
          <DraggableTextArea
            id="custom_query"
            value={searchCriteria.custom_query}
            onChange={(e) =>
              updateSearchCriteriaField("custom_query", e.target.value)
            }
            placeholder="e.g., has:nouserlabels -in:Sent"
            className="h-20 font-mono text-xs w-full resize-none"
          />
          <p className="text-xs text-muted-foreground break-words">
            Enter raw Gmail search query (overrides other filters).
          </p>
        </div>
      </NodeConfigPanel>
      <DataSourceDialog
        isOpen={isCreateDataSourceOpen}
        onOpenChange={setIsCreateDataSourceOpen}
        onDataSourceSaved={(created) => {
          if (created?.id) setDataSourceId(created.id);
        }}
        mode="create"
        defaultSourceType="gmail"
      />
    </>
  );
};
