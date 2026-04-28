import React, { useEffect, useState } from "react";
import { HumanInTheLoopNodeData, HumanInTheLoopFormField } from "../types/nodes";
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
import { Switch } from "@/components/switch";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/dialog";
import { Plus, Pencil, Trash2, Save } from "lucide-react";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { DraggableTextArea } from "../components/custom/DraggableTextArea";

const FIELD_TYPES = [
  { value: "text", label: "Text" },
  { value: "number", label: "Number" },
  { value: "select", label: "Select" },
  { value: "boolean", label: "Checkbox" },
  { value: "date", label: "Date" },
] as const;

const emptyField: HumanInTheLoopFormField = {
  name: "",
  type: "text",
  label: "",
  required: false,
  placeholder: "",
  description: "",
  options: [],
};

interface FieldDialogState {
  isOpen: boolean;
  mode: "add" | "edit";
  editIndex: number | null;
  field: HumanInTheLoopFormField;
}

export const HumanInTheLoopDialog: React.FC<
  BaseNodeDialogProps<HumanInTheLoopNodeData, HumanInTheLoopNodeData>
> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const [name, setName] = useState(data.name || "");
  const [message, setMessage] = useState(
    data.message || "Please provide the following information:"
  );
  const [askOnce, setAskOnce] = useState(data.ask_once !== false);
  const [formFields, setFormFields] = useState<HumanInTheLoopFormField[]>(
    data.form_fields || []
  );
  const [fieldDialog, setFieldDialog] = useState<FieldDialogState>({
    isOpen: false,
    mode: "add",
    editIndex: null,
    field: { ...emptyField },
  });

  useEffect(() => {
    if (isOpen) {
      setName(data.name || "");
      setMessage(data.message || "Please provide the following information:");
      setAskOnce(data.ask_once !== false);
      setFormFields(data.form_fields || []);
    }
  }, [isOpen, data]);

  const handleSave = () => {
    onUpdate({
      ...data,
      name,
      message,
      ask_once: askOnce,
      form_fields: formFields,
    });
    onClose();
  };

  // Field CRUD
  const openAddFieldDialog = () => {
    setFieldDialog({
      isOpen: true,
      mode: "add",
      editIndex: null,
      field: { ...emptyField },
    });
  };

  const openEditFieldDialog = (index: number) => {
    setFieldDialog({
      isOpen: true,
      mode: "edit",
      editIndex: index,
      field: { ...formFields[index] },
    });
  };

  const handleSaveField = () => {
    const field = fieldDialog.field;
    if (!field.name || !field.label) return;

    if (fieldDialog.mode === "add") {
      setFormFields((prev) => [...prev, field]);
    } else if (fieldDialog.editIndex !== null) {
      setFormFields((prev) =>
        prev.map((f, i) => (i === fieldDialog.editIndex ? field : f))
      );
    }
    setFieldDialog((prev) => ({ ...prev, isOpen: false }));
  };

  const handleDeleteField = (index: number) => {
    setFormFields((prev) => prev.filter((_, i) => i !== index));
  };

  const updateDialogField = (
    key: keyof HumanInTheLoopFormField,
    value: unknown
  ) => {
    setFieldDialog((prev) => ({
      ...prev,
      field: { ...prev.field, [key]: value },
    }));
  };

  // Select options management
  const addOption = () => {
    updateDialogField("options", [
      ...(fieldDialog.field.options || []),
      { value: "", label: "" },
    ]);
  };

  const updateOption = (
    optIndex: number,
    key: "value" | "label",
    val: string
  ) => {
    const newOptions = [...(fieldDialog.field.options || [])];
    newOptions[optIndex] = { ...newOptions[optIndex], [key]: val };
    updateDialogField("options", newOptions);
  };

  const removeOption = (optIndex: number) => {
    updateDialogField(
      "options",
      (fieldDialog.field.options || []).filter((_, i) => i !== optIndex)
    );
  };

  return (
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
      data={{
        ...data,
        name,
        message,
        ask_once: askOnce,
        form_fields: formFields,
      }}
    >
      <div className="space-y-2">
        <Label htmlFor="name">Name</Label>
        <RichInput
          id="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Human In The Loop"
          className="break-all w-full"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="message">Message</Label>
        <DraggableTextArea
          id="message"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Message shown above the form..."
          className="text-sm h-20 resize-none w-full"
        />
      </div>

      <div className="flex items-center justify-between">
        <div>
          <Label htmlFor="ask_once" className="text-sm font-medium">Ask once per conversation</Label>
          <p className="text-xs text-muted-foreground">When enabled, input is collected only once. Subsequent executions use the cached response.</p>
        </div>
        <Switch
          id="ask_once"
          checked={askOnce}
          onCheckedChange={(val) => setAskOnce(val)}
        />
      </div>

      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <Label>Form Fields ({formFields.length})</Label>
          <Button
            size="sm"
            variant="outline"
            className="h-6 text-xs"
            onClick={openAddFieldDialog}
          >
            <Plus className="h-3 w-3 mr-1" /> Add Field
          </Button>
        </div>

        <div className="space-y-2">
          {formFields.map((field, index) => (
            <div
              key={index}
              className="flex items-center justify-between gap-2 p-2.5 bg-gray-50 rounded-lg border"
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-sm font-medium truncate">
                  {field.label}
                </span>
                <span className="text-xs text-muted-foreground px-1.5 py-0.5 bg-gray-200 rounded">
                  {field.type}
                </span>
                {field.required && (
                  <span className="text-red-500 text-xs">*</span>
                )}
              </div>
              <div className="flex items-center gap-1 flex-shrink-0">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => openEditFieldDialog(index)}
                >
                  <Pencil className="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-red-500 hover:text-red-700"
                  onClick={() => handleDeleteField(index)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          ))}

          {formFields.length === 0 && (
            <div className="text-sm text-muted-foreground italic text-center py-4 border border-dashed rounded-lg">
              No fields configured. Click &quot;Add Field&quot; to get started.
            </div>
          )}
        </div>
      </div>

      {/* Field Editor Dialog — rendered inside NodeConfigPanel so the Sheet doesn't close */}
      <Dialog
        open={fieldDialog.isOpen}
        onOpenChange={(open) =>
          setFieldDialog((prev) => ({ ...prev, isOpen: open }))
        }
      >
        <DialogContent className="max-w-md" style={{ zIndex: 2000 }}>
          <DialogHeader>
            <DialogTitle>
              {fieldDialog.mode === "add" ? "Add Field" : "Edit Field"}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">Field Name (key)</Label>
                <RichInput
                  value={fieldDialog.field.name}
                  onChange={(e) => updateDialogField("name", e.target.value)}
                  placeholder="e.g. location"
                  className="text-sm"
                />
              </div>
              <div>
                <Label className="text-xs">Label</Label>
                <RichInput
                  value={fieldDialog.field.label}
                  onChange={(e) => updateDialogField("label", e.target.value)}
                  placeholder="e.g. Your Location"
                  className="text-sm"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">Type</Label>
                <Select
                  value={fieldDialog.field.type}
                  onValueChange={(val) => updateDialogField("type", val)}
                >
                  <SelectTrigger className="text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="z-[2100]">
                    {FIELD_TYPES.map((ft) => (
                      <SelectItem key={ft.value} value={ft.value}>
                        {ft.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-end gap-2 pb-1">
                <Switch
                  checked={fieldDialog.field.required || false}
                  onCheckedChange={(val) => updateDialogField("required", val)}
                />
                <Label className="text-xs">Required</Label>
              </div>
            </div>

            <div>
              <Label className="text-xs">Placeholder</Label>
              <RichInput
                value={fieldDialog.field.placeholder || ""}
                onChange={(e) =>
                  updateDialogField("placeholder", e.target.value)
                }
                placeholder="Placeholder text..."
                className="text-sm"
              />
            </div>

            <div>
              <Label className="text-xs">Description</Label>
              <RichInput
                value={fieldDialog.field.description || ""}
                onChange={(e) =>
                  updateDialogField("description", e.target.value)
                }
                placeholder="Help text for this field..."
                className="text-sm"
              />
            </div>

            {/* Options editor for select type */}
            {fieldDialog.field.type === "select" && (
              <div>
                <Label className="text-xs mb-1 block">Options</Label>
                <div className="space-y-1">
                  {(fieldDialog.field.options || []).map((opt, optIdx) => (
                    <div key={optIdx} className="flex items-center gap-1">
                      <RichInput
                        value={opt.value}
                        onChange={(e) =>
                          updateOption(optIdx, "value", e.target.value)
                        }
                        placeholder="Value"
                        className="text-xs h-7"
                      />
                      <RichInput
                        value={opt.label}
                        onChange={(e) =>
                          updateOption(optIdx, "label", e.target.value)
                        }
                        placeholder="Label"
                        className="text-xs h-7"
                      />
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 flex-shrink-0 text-red-500"
                        onClick={() => removeOption(optIdx)}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  ))}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-1 text-xs h-6"
                  onClick={addOption}
                >
                  <Plus className="h-3 w-3 mr-1" />
                  Add Option
                </Button>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() =>
                setFieldDialog((prev) => ({ ...prev, isOpen: false }))
              }
            >
              Cancel
            </Button>
            <Button
              onClick={handleSaveField}
              disabled={!fieldDialog.field.name || !fieldDialog.field.label}
            >
              {fieldDialog.mode === "add" ? "Add" : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </NodeConfigPanel>
  );
};
