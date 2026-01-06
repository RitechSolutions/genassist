import React, { useState, useEffect } from "react";
import { CalendarEventToolNodeData } from "../types/nodes";
import { DataSource } from "@/interfaces/dataSource.interface";
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
import { Save } from "lucide-react";
import { NodeConfigDialog } from "../components/NodeConfigDialog";
import { DraggableInput } from "../components/custom/DraggableInput";
import { BaseNodeDialogProps } from "./base";
import { DataSourceDialog } from "@/views/DataSources/components/DataSourceDialog";
import { CreateNewSelectItem } from "@/components/CreateNewSelectItem";

interface CalendarEventDialogProps
  extends BaseNodeDialogProps<
    CalendarEventToolNodeData,
    CalendarEventToolNodeData
  > {
  connectors: DataSource[];
}

export const CalendarEventDialog: React.FC<CalendarEventDialogProps> = (
  props
) => {
  const { isOpen, onClose, data, onUpdate, connectors } = props;

  const [name, setName] = useState(data.name || "");
  const [summary, setSummary] = useState(data.summary || "");
  const [start, setStart] = useState(data.start || "");
  const [end, setEnd] = useState(data.end || "");
  const [operation, setOperation] = useState(data.operation || "");
  const [dataSourceId, setDataSourceId] = useState(
    data.dataSourceId?.toString() || ""
  );
  const [subjectContains, setSubjectContains] = useState(
    data.subjectContains || ""
  );
  const [isCreateDataSourceOpen, setIsCreateDataSourceOpen] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setName(data.name || "");
      setSummary(data.summary || "");
      setStart(data.start || "");
      setEnd(data.end || "");
      setOperation(data.operation || "");
      setDataSourceId(data.dataSourceId?.toString() || "");
      setSubjectContains(data.subjectContains || "");
    }
  }, [isOpen, data]);

  const handleSave = () => {
    onUpdate({
      ...data,
      name,
      summary,
      start,
      end,
      operation,
      dataSourceId,
      subjectContains,
    });
    onClose();
  };

  return (
    <>
      <NodeConfigDialog
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
          summary,
          start,
          end,
          operation,
          dataSourceId,
          subjectContains,
        }}
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
          <Label htmlFor="connector-select">Select Connector</Label>
          <Select
            value={dataSourceId}
            onValueChange={(val) => {
              if (val === "__create__") {
                setIsCreateDataSourceOpen(true);
                return;
              }
              setDataSourceId(val);
            }}
          >
            <SelectTrigger id="connector-select">
              <SelectValue placeholder="Select connector" />
            </SelectTrigger>
            <SelectContent>
              {connectors.map((conn) => (
                <SelectItem key={conn.id} value={String(conn.id)}>
                  {conn.name}
                </SelectItem>
              ))}
              <CreateNewSelectItem />
            </SelectContent>
          </Select>

          <div className="space-y-2">
            <Label className="font-bold">Calendar Event</Label>
            <div className="space-y-2">
              <div className="space-y-2">
                <Label htmlFor="summary">Summary</Label>
                <DraggableInput
                  id="summary"
                  type="text"
                  value={summary}
                  onChange={(e) => setSummary(e.target.value)}
                  placeholder="e.g., General assembly meeting"
                  className="w-full"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="operation-select">Operation</Label>
                <Select
                  value={operation}
                  onValueChange={(val) => setOperation(val)}
                >
                  <SelectTrigger id="operation-select">
                    <SelectValue placeholder="Select operation" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="create_calendar_event">
                      Create event
                    </SelectItem>
                    <SelectItem value="search_calendar_events">
                      Search event
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label htmlFor="start">Start</Label>
                  <DraggableInput
                    id="start"
                    type="datetime"
                    value={start}
                    onChange={(e) => setStart(e.target.value)}
                    placeholder="e.g., 2025-07-22T19:41:00"
                    className="w-full"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="end">End</Label>
                  <DraggableInput
                    id="end"
                    type="datetime"
                    value={end}
                    onChange={(e) => setEnd(e.target.value)}
                    placeholder="e.g., 2025-07-22T19:51:00"
                    className="w-full"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="query">Subject Contains</Label>
                <DraggableInput
                  id="subjectContains"
                  type="text"
                  value={subjectContains}
                  onChange={(e) => setSubjectContains(e.target.value)}
                  placeholder="e.g., Fundraiser"
                  className="w-full"
                />
              </div>
            </div>
          </div>
        </div>
      </NodeConfigDialog>
      <DataSourceDialog
        isOpen={isCreateDataSourceOpen}
        onOpenChange={setIsCreateDataSourceOpen}
        onDataSourceSaved={(created) => {
          if (created?.id) setDataSourceId(created.id);
        }}
        mode="create"
      />
    </>
  );
};
