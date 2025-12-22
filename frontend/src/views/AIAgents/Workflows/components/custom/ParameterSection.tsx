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
import { NodeSchema, SchemaField, SchemaType } from "../../types/schemas";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/dropdown-menu";
import { useChatInputSchema } from "../../hooks/useChatInputSchema";
import { Label } from "@/components/label";

interface ParameterSectionProps {
  label?: string;
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
  suggestParams?: boolean;
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
  suggestedParams?: NodeSchema;
}

interface ParameterBadgesProps {
  params: Record<string, { type: string; required?: boolean }>;
  className?: string;
}

export const ParameterBadges: FC<ParameterBadgesProps> = ({
  params,
  className = "",
}) => {
  const chatInputSchema = useChatInputSchema();
  const suggestedParams = chatInputSchema || {};
  return (
    <div className={`flex flex-wrap gap-2 ${className}`}>
      {Object.entries(params ?? {})
        .filter(([name, param]) => !suggestedParams[name])
        .map(([name, param]) => (
          <Badge
            key={name}
            variant="secondary"
            className="cursor-pointer hover:bg-secondary/80"
          >
            {name}
          </Badge>
        ))}
      {Object.entries(params ?? {})
        .filter(([name, param]) => suggestedParams[name])
        .map(([name, param]) => (
          <Badge
            key={name}
            variant="secondary"
            className="cursor-pointer hover:bg-secondary/80 font-light"
          >
            {name}
          </Badge>
        ))}
      {Object.keys(params || {}).length === 0 && (
        <span className="text-sm text-gray-400 italic">
          No variables required
        </span>
      )}
    </div>
  );
};

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
    defaultValue?: string;
  }>({
    name: "",
    type: "string",
    description: "",
    required: false,
    defaultValue: "",
  });

  useEffect(() => {
    if (isOpen) {
      if (paramName && param) {
        setFormData({
          name: paramName,
          type: param.type,
          description: param.description || "",
          required: param.required || false,
          defaultValue: param.defaultValue || "",
        });
      } else {
        setFormData({
          name: "",
          type: "string",
          description: "",
          required: false,
          defaultValue: "",
        });
      }
    }
  }, [isOpen, mode, paramName, param]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave(formData.name, {
      type: formData.type,
      description: formData.description,
      required: formData.required,
      defaultValue: formData.defaultValue,
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
              className="w-full"
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
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {["string", "number", "boolean", "object", "array", "any"].map(
                  (t) => (
                    <SelectItem key={t} value={t}>
                      {t.charAt(0).toUpperCase() + t.slice(1)}
                    </SelectItem>
                  )
                )}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Description</label>
            <Input
              placeholder="Parameter description"
              value={formData.description}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  description: e.target.value,
                }))
              }
              className="w-full"
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
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="true">Yes</SelectItem>
                <SelectItem value="false">No</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Default Value</label>
            <Input
              placeholder="Default value (optional)"
              value={formData.defaultValue || ""}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  defaultValue: e.target.value,
                }))
              }
              className="w-full"
            />
          </div>
          <DialogFooter className="flex justify-between">
            {mode === "edit" && onDelete && (
              <Button
                type="button"
                variant="destructive"
                onClick={handleDelete}
                // disabled={totalParams <= 1}
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
  label,
  dynamicParams,
  setDynamicParams,
  addItem,
  removeItem,
  suggestParams = false,
}) => {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedParamName, setSelectedParamName] = useState<string | null>(
    null
  );
  const [dialogMode, setDialogMode] = useState<"edit" | "create">("create");
  const chatInputSchema = useChatInputSchema();
  const suggestedParams = suggestParams ? chatInputSchema : {};
  const handleParamClick = (name: string) => {
    setSelectedParamName(name);
    setDialogMode("edit");
    setDialogOpen(true);
  };

  // Handles adding a suggested param or opening dialog for new
  const handleAddSelect = (selected: string) => {
    if (selected === "__add_new__") {
      setSelectedParamName(null);
      setDialogMode("create");
      setDialogOpen(true);
    } else if (suggestedParams?.[selected]) {
      setDynamicParams((prev) => ({
        ...prev,
        [selected]: suggestedParams[selected],
      }));
    }
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
    <div className="flex flex-col gap-1 py-1 w-full min-w-0">
      {label && <Label htmlFor="parameters">{label}</Label>}

      <div className="flex flex-wrap gap-2 items-center min-w-0">
        {Object.entries(dynamicParams ?? {})
          .filter(([name, param]) => !suggestedParams[name])
          .map(([name, param]) => (
            <Badge
              key={name}
              variant="secondary"
              className="cursor-pointer hover:bg-secondary/80 break-words"
              onClick={() => handleParamClick(name)}
            >
              {name}
            </Badge>
          ))}
        {Object.entries(dynamicParams ?? {})
          .filter(([name, param]) => suggestedParams[name])
          .map(([name, param]) => (
            <Badge
              key={name}
              variant="secondary"
              className="cursor-pointer hover:bg-secondary/80 font-light break-words"
              onClick={() => handleParamClick(name)}
            >
              {name}
            </Badge>
          ))}
        {/* Add Parameter DropdownMenu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="p-0 border-none bg-none outline-none"
              style={{ background: "none" }}
            >
              <Badge
                variant="outline"
                className="cursor-pointer hover:bg-secondary/80 flex items-center gap-1"
              >
                <Plus className="w-3 h-3" />
                Add Parameter
              </Badge>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            {Object.entries(suggestedParams).map(([name, s]) => (
              <DropdownMenuItem
                key={name}
                onSelect={() => handleAddSelect(name)}
                className="break-words"
              >
                {name} ({s.type}) - {s.description}
              </DropdownMenuItem>
            ))}
            <DropdownMenuItem
              onSelect={() => handleAddSelect("__add_new__")}
              className="font-semibold"
            >
              + Add new...
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <ParameterDialog
        isOpen={dialogOpen}
        onOpenChange={setDialogOpen}
        paramName={selectedParamName}
        param={selectedParamName ? dynamicParams[selectedParamName] : null}
        onSave={handleSave}
        onDelete={handleDelete}
        mode={dialogMode}
        totalParams={Object.keys(dynamicParams ?? {}).length}
      />
    </div>
  );
};
