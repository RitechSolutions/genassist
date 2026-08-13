import React, { useState } from "react";
import { CalendarEventToolNodeData } from "../types/nodes";
import { DataSource } from "@/interfaces/dataSource.interface";
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
import { Save } from "lucide-react";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { DraggableInput } from "../components/custom/DraggableInput";
import { BaseNodeDialogProps } from "./base";
import { DataSourceDialog } from "@/views/DataSources/components/DataSourceDialog";
import { CreateNewSelectItem } from "@/components/CreateNewSelectItem";
import { useNodeDialogState } from "./useNodeDialogState";

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
  const { onClose, data, connectors } = props;

  const { values, setField, merged, handleSave } = useNodeDialogState(
    props,
    () => ({
      name: data.name || "",
      summary: data.summary || "",
      start: data.start || "",
      end: data.end || "",
      operation: data.operation || "",
      dataSourceId: data.dataSourceId?.toString() || "",
      subjectContains: data.subjectContains || "",
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "",
    })
  );

  const [isCreateDataSourceOpen, setIsCreateDataSourceOpen] = useState(false);

  return (
    <>
      <NodeConfigPanel
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
        data={merged}
      >
        <div className="space-y-2">
          <Label htmlFor="node-name">Node Name</Label>
          <RichInput
            id="node-name"
            value={values.name}
            onChange={(e) => setField("name", e.target.value)}
            placeholder="Enter the name of this node"
            className="w-full"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="connector-select">Select Connector</Label>
          <Select
            value={values.dataSourceId}
            onValueChange={(val) => {
              if (val === "__create__") {
                setIsCreateDataSourceOpen(true);
                return;
              }
              setField("dataSourceId", val);
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
                  value={values.summary}
                  onChange={(e) => setField("summary", e.target.value)}
                  placeholder="e.g., General assembly meeting"
                  className="w-full"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="operation-select">Operation</Label>
                <Select
                  value={values.operation}
                  onValueChange={(val) => setField("operation", val)}
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
                    value={values.start}
                    onChange={(e) => setField("start", e.target.value)}
                    placeholder="e.g., 2025-07-22T19:41:00"
                    className="w-full"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="end">End</Label>
                  <DraggableInput
                    id="end"
                    type="datetime"
                    value={values.end}
                    onChange={(e) => setField("end", e.target.value)}
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
                  value={values.subjectContains}
                  onChange={(e) => setField("subjectContains", e.target.value)}
                  placeholder="e.g., Fundraiser"
                  className="w-full"
                />
              </div>
            </div>
          </div>
        </div>
      </NodeConfigPanel>
      <DataSourceDialog
        isOpen={isCreateDataSourceOpen}
        onOpenChange={setIsCreateDataSourceOpen}
        onDataSourceSaved={(created) => {
          if (created?.id) setField("dataSourceId", created.id);
        }}
        mode="create"
      />
    </>
  );
};
