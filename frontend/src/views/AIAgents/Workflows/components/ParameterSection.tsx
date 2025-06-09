import { FC, useState, useEffect } from "react";
import { Button } from "@/components/button";
import { Plus } from "lucide-react";
import { Input } from "@/components/input";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/select";
import { Badge } from "@/components/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/dialog";
import { NodeSchema, SchemaField, SchemaType } from "../types/schemas";

interface ParameterSectionProps {
  dynamicParams: NodeSchema;
  setDynamicParams: React.Dispatch<React.SetStateAction<NodeSchema>>;
  addItem: (
    setter: React.Dispatch<React.SetStateAction<NodeSchema>>,
    template: SchemaField
  ) => void;
  removeItem: (
    setter: React.Dispatch<React.SetStateAction<NodeSchema>>,
    name: string
  ) => void;
}

interface ParameterDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  paramName: string | null;
  param: SchemaField | null;
  onSave: (name: string, param: SchemaField) => void;
  onDelete?: (name: string) => void;
  mode: "edit" | "create";
  totalParams: number;
}

const ParameterDialog: FC<ParameterDialogProps> = ({
  isOpen,
  onOpenChange,
  paramName,
  param,
  onSave,
  onDelete,
  mode,
  totalParams,
}) => {
  const [formData, setFormData] = useState<{
    name: string;
    type: SchemaType;
    description: string;
    required: boolean;
  }>({
    name: paramName || "",
    type: param?.type || "string",
    description: param?.description || "",
    required: param?.required || false,
  });

  useEffect(() => {
    if (paramName && param) {
      setFormData({
        name: paramName,
        type: param.type,
        description: param.description || "",
        required: param.required || false,
      });
    }
  }, [paramName, param]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave(formData.name, {
      type: formData.type,
      description: formData.description,
      required: formData.required,
    });
    onOpenChange(false);
  };

  const handleDelete = () => {
    if (paramName && onDelete) {
      onDelete(paramName);
      onOpenChange(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {mode === "create" ? "Add Parameter" : "Edit Parameter"}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Parameter Name</label>
            <Input
              placeholder="param_1"
              value={formData.name}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, name: e.target.value }))
              }
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Type</label>
            <Select
              value={formData.type}
              onValueChange={(v) =>
                setFormData((prev) => ({ ...prev, type: v as SchemaType }))
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {["string", "number", "boolean", "object", "array", "any"].map((t) => (
                  <SelectItem key={t} value={t}>
                    {t.charAt(0).toUpperCase() + t.slice(1)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Description</label>
            <Input
              placeholder="Parameter description"
              value={formData.description}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, description: e.target.value }))
              }
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Required</label>
            <Select
              value={formData.required ? "true" : "false"}
              onValueChange={(v) =>
                setFormData((prev) => ({ ...prev, required: v === "true" }))
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="true">Yes</SelectItem>
                <SelectItem value="false">No</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <DialogFooter className="flex justify-between">
            {mode === "edit" && onDelete && (
              <Button
                type="button"
                variant="destructive"
                onClick={handleDelete}
                disabled={totalParams <= 1}
              >
                Delete Parameter
              </Button>
            )}
            <Button type="submit">
              {mode === "create" ? "Add Parameter" : "Save Changes"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export const ParameterSection: FC<ParameterSectionProps> = ({
  dynamicParams,
  setDynamicParams,
  addItem,
  removeItem,
}) => {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedParamName, setSelectedParamName] = useState<string | null>(null);
  const [dialogMode, setDialogMode] = useState<"edit" | "create">("create");

  const handleParamClick = (name: string) => {
    setSelectedParamName(name);
    setDialogMode("edit");
    setDialogOpen(true);
  };

  const handleAddClick = () => {
    setSelectedParamName(null);
    setDialogMode("create");
    setDialogOpen(true);
  };

  const handleSave = (name: string, paramData: SchemaField) => {
    if (dialogMode === "create") {
      setDynamicParams((prev) => ({
        ...prev,
        [name]: paramData,
      }));
    } else if (selectedParamName) {
      setDynamicParams((prev) => {
        const newParams = { ...prev };
        if (name !== selectedParamName) {
          delete newParams[selectedParamName];
        }
        newParams[name] = paramData;
        return newParams;
      });
    }
  };

  const handleDelete = (name: string) => {
    removeItem(setDynamicParams, name);
  };

  return (
    <div className="flex flex-col gap-4 py-4">
      <div className="flex flex-wrap gap-2">
        {Object.entries(dynamicParams).map(([name, param]) => (
          <Badge
            key={name}
            variant="secondary"
            className="cursor-pointer hover:bg-secondary/80"
            onClick={() => handleParamClick(name)}
          >
            {name}
          </Badge>
        ))}
        <Badge
          variant="outline"
          className="cursor-pointer hover:bg-secondary/80 flex items-center gap-1"
          onClick={handleAddClick}
        >
          <Plus className="w-3 h-3" />
          Add Parameter
        </Badge>
      </div>

      <ParameterDialog
        isOpen={dialogOpen}
        onOpenChange={setDialogOpen}
        paramName={selectedParamName}
        param={selectedParamName ? dynamicParams[selectedParamName] : null}
        onSave={handleSave}
        onDelete={handleDelete}
        mode={dialogMode}
        totalParams={Object.keys(dynamicParams).length}
      />
    </div>
  );
};
