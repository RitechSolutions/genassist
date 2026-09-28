import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { HumanInTheLoopNodeData, HumanInTheLoopFormField } from "../types/nodes";
import { Button } from "@/components/button";
import { RichInput } from "@/components/richInput";
import { RichTextarea } from "@/components/richTextarea";
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
import { TranslationTrigger } from "../../components/TranslationTrigger";
import { getLanguages } from "@/services/translations";
import { Language } from "@/interfaces/translation.interface";
import { useNodeDialogState } from "./useNodeDialogState";

const FIELD_TYPES = [
  { value: "text", label: "Text" },
  // "Long text" is intentionally not offered yet: the deployed chat widget is
  // genassist-chat-react 1.0.42, which has no textarea branch. Re-add this once
  // a build carrying the new field type is published and consumers have upgraded.
  // { value: "textarea", label: "Long text" },
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
  const { isOpen, onClose, data, nodeId } = props;
  const { agentId } = useParams<{ agentId: string }>();

  // Active languages, loaded once per open so each per-field trigger reuses the same list.
  const [languages, setLanguages] = useState<Language[]>([]);

  // Translation keys are scoped under the agent + node so they never collide with other
  // nodes or with agent-level keys, while keeping the `agent.{id}.` prefix the chat
  // language selector already aggregates. null when the node/agent context is unknown.
  const nodePrefix =
    agentId && nodeId ? `agent.${agentId}.node.${nodeId}` : null;
  const fieldKey = (fieldName: string, attr: string) =>
    `${nodePrefix}.fields.${fieldName}.${attr}`;

  const { values, setField, setValues, merged, handleSave } =
    useNodeDialogState(
      props,
      () => ({
        name: data.name || "",
        message: data.message || "Please provide the following information:",
        askOnce: data.ask_once !== false,
        formFields: data.form_fields || [],
      }),
      (v) => ({
        name: v.name,
        message: v.message,
        ask_once: v.askOnce,
        form_fields: v.formFields,
      })
    );

  const [fieldDialog, setFieldDialog] = useState<FieldDialogState>({
    isOpen: false,
    mode: "add",
    editIndex: null,
    field: { ...emptyField },
  });

  // Load the active language list once when the panel opens (only when translations are
  // actually usable, i.e. the agent/node context is known), shared by every trigger.
  useEffect(() => {
    if (isOpen && nodePrefix && languages.length === 0) {
      getLanguages()
        .then(setLanguages)
        .catch(() => {
          /* non-fatal: dialog still opens, triggers will self-fetch if needed */
        });
    }
  }, [isOpen, nodePrefix, languages.length]);

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
      field: { ...values.formFields[index] },
    });
  };

  const handleSaveField = () => {
    const field = fieldDialog.field;
    if (!field.name || !field.label) return;

    if (fieldDialog.mode === "add") {
      setValues((prev) => ({ ...prev, formFields: [...prev.formFields, field] }));
    } else if (fieldDialog.editIndex !== null) {
      setValues((prev) => ({
        ...prev,
        formFields: prev.formFields.map((f, i) =>
          i === fieldDialog.editIndex ? field : f
        ),
      }));
    }
    setFieldDialog((prev) => ({ ...prev, isOpen: false }));
  };

  const handleDeleteField = (index: number) => {
    setValues((prev) => ({
      ...prev,
      formFields: prev.formFields.filter((_, i) => i !== index),
    }));
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
      data={merged}
    >
      <div className="space-y-2">
        <Label htmlFor="name">Name</Label>
        <RichInput
          id="name"
          value={values.name}
          onChange={(e) => setField("name", e.target.value)}
          placeholder="Human In The Loop"
          className="break-all w-full"
        />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <Label htmlFor="message">Message</Label>
          {nodePrefix && values.message.trim() && (
            <TranslationTrigger
              translationKey={`${nodePrefix}.message`}
              currentValue={values.message}
              languages={languages}
            />
          )}
        </div>
        <DraggableTextArea
          id="message"
          value={values.message}
          onChange={(e) => setField("message", e.target.value)}
          placeholder="Message shown above the form..."
          size="body"
          className="text-sm w-full"
        />
      </div>

      <div className="flex items-center justify-between">
        <div>
          <Label htmlFor="ask_once" className="text-sm font-medium">Ask once per conversation</Label>
          <p className="text-xs text-muted-foreground">When enabled, input is collected only once. Subsequent executions use the cached response.</p>
        </div>
        <Switch
          id="ask_once"
          checked={values.askOnce}
          onCheckedChange={(val) => setField("askOnce", val)}
        />
      </div>

      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <Label>Form Fields ({values.formFields.length})</Label>
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
          {values.formFields.map((field, index) => (
            <div
              key={index}
              className="p-2.5 bg-muted rounded-lg border space-y-2"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-sm font-medium truncate">
                    {field.label}
                  </span>
                  <span className="text-xs text-muted-foreground px-1.5 py-0.5 bg-muted rounded">
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

              {/* Per-field translation triggers — same UX as agent fields, scoped to this
                  node + field. Only shown once the field has a name (its key segment). */}
              {nodePrefix && field.name && (
                <div className="flex flex-wrap items-center gap-1.5 pt-1.5 border-t border-border">
                  <span className="text-xs text-muted-foreground mr-0.5">
                    Translate:
                  </span>
                  {field.label && (
                    <TranslationTrigger
                      label="Label"
                      translationKey={fieldKey(field.name, "label")}
                      currentValue={field.label}
                      languages={languages}
                    />
                  )}
                  {field.placeholder && (
                    <TranslationTrigger
                      label="Placeholder"
                      translationKey={fieldKey(field.name, "placeholder")}
                      currentValue={field.placeholder}
                      languages={languages}
                    />
                  )}
                  {field.description && (
                    <TranslationTrigger
                      label="Description"
                      translationKey={fieldKey(field.name, "description")}
                      currentValue={field.description}
                      languages={languages}
                    />
                  )}
                  {(field.options || [])
                    .filter((opt) => opt.value && opt.label)
                    .map((opt) => (
                      <TranslationTrigger
                        key={opt.value}
                        label={`Option: ${opt.label}`}
                        translationKey={`${fieldKey(field.name, "options")}.${opt.value}.label`}
                        currentValue={opt.label}
                        languages={languages}
                      />
                    ))}
                </div>
              )}
            </div>
          ))}

          {values.formFields.length === 0 && (
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
              <RichTextarea
                size="hint"
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
