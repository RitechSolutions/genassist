import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/dialog";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import {
  createDataSource,
  getDataSourceSchemas,
  updateDataSource,
} from "@/services/dataSources";
import { Switch } from "@/components/switch";
import { Label } from "@/components/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { toast } from "react-hot-toast";
import { Loader2 } from "lucide-react";
import { DataSource, DataSourceField } from "@/interfaces/dataSource.interface";
import { useQuery } from "@tanstack/react-query";

interface DataSourceDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onDataSourceSaved: () => void;
  dataSourceToEdit?: DataSource | null;
  mode?: "create" | "edit";
}

export function DataSourceDialog({
  isOpen,
  onOpenChange,
  onDataSourceSaved,
  dataSourceToEdit = null,
  mode = "create",
}: DataSourceDialogProps) {
  const [name, setName] = useState("");
  const [sourceType, setSourceType] = useState("");
  const [connectionData, setConnectionData] = useState<
    Record<string, string | number>
  >({});
  const [isActive, setIsActive] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [dataSourceId, setDataSourceId] = useState<string | undefined>("");
  const [showAdvanced, setShowAdvanced] = useState(false);

  const { data, isLoading: isLoadingConfig } = useQuery({
    queryKey: ["dataSourceSchemas"],
    queryFn: () => getDataSourceSchemas(),
    refetchInterval: 5000,
    refetchOnWindowFocus: false,
    staleTime: 3000,
  });

  const dataSourceSchemas = data ?? {};

  useEffect(() => {
    if (isOpen) {
      resetForm();
      if (dataSourceToEdit && mode === "edit") {
        populateFormWithDataSource(dataSourceToEdit);
      }
    }
  }, [isOpen, dataSourceToEdit, mode]);

  const resetForm = () => {
    setDataSourceId(undefined);
    setName("");
    setSourceType("");
    setConnectionData({});
    setIsActive(true);
    setShowAdvanced(false);
  };

  const populateFormWithDataSource = (dataSource: DataSource) => {
    setDataSourceId(dataSource.id);
    setName(dataSource.name);
    setSourceType(dataSource.source_type);
    setConnectionData(dataSource.connection_data);
    setIsActive(dataSource.is_active === 1);
  };

  const handleConnectionDataChange = (
    field: DataSourceField,
    value: string | number
  ) => {
    setConnectionData((prev) => ({
      ...prev,
      [field.name]: value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!name || !sourceType) {
      toast.error("Name and source type are required");
      return;
    }

    const schema = dataSourceSchemas[sourceType];
    if (!schema) {
      toast.error("Invalid source type");
      return;
    }

    const missingFields = schema.fields
      .filter((field) => field.required && !connectionData[field.name])
      .map((field) => field.label);

    if (missingFields.length > 0) {
      toast.error(`Missing required fields: ${missingFields.join(", ")}`);
      return;
    }

    setIsSubmitting(true);
    try {
      const data: Partial<DataSource> = {
        name,
        source_type: sourceType,
        connection_data: connectionData,
        is_active: isActive ? 1 : 0,
      };

      if (mode === "create") {
        await createDataSource(data as DataSource);
        toast.success("Data Source created");
      } else {
        if (!dataSourceId) throw new Error("Missing data source ID");
        await updateDataSource(dataSourceId, data);
        toast.success("Data Source updated");
      }

      onDataSourceSaved();
      onOpenChange(false);
      resetForm();
    } catch (error) {
      toast.error(`Failed to ${mode} data source`);
      console.error(error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderField = (field: DataSourceField) => {
    const value = connectionData[field.name] ?? field.default;

    switch (field.type) {
      case "number":
        return (
          <Input
            type="number"
            value={value as number}
            onChange={(e) =>
              handleConnectionDataChange(field, parseFloat(e.target.value))
            }
            // min={field.min}
            // max={field.max}
            // step={field.step}
            placeholder={field.label}
          />
        );
      case "password":
        return (
          <Input
            type="password"
            value={value as string}
            onChange={(e) => handleConnectionDataChange(field, e.target.value)}
            placeholder={field.label}
          />
        );
      default:
        return (
          <Input
            type="text"
            value={value as string}
            onChange={(e) => handleConnectionDataChange(field, e.target.value)}
            placeholder={field.label}
          />
        );
    }
  };

  const requiredFields =
    dataSourceSchemas[sourceType]?.fields.filter((f) => f.required) ?? [];
  const optionalFields =
    dataSourceSchemas[sourceType]?.fields.filter((f) => !f.required) ?? [];

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {mode === "create" ? "Create Data Source" : "Edit Data Source"}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Name"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="source_type">Source Type</Label>
            {isLoadingConfig ? (
              <div className="flex items-center justify-center p-4">
                <Loader2 className="w-6 h-6 animate-spin" />
              </div>
            ) : (
              <Select
                value={sourceType}
                onValueChange={(value) => {
                  setSourceType(value);
                  setConnectionData({});
                }}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select Source Type" />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(dataSourceSchemas).map(([type, schema]) => (
                    <SelectItem key={type} value={type}>
                      {schema.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>

          {sourceType && (
            <>
              <div className="space-y-4">
                {requiredFields.map((field) => (
                  <div key={field.name} className="space-y-2">
                    <Label htmlFor={field.name}>
                      {field.label}
                      {field.required && (
                        <span className="text-red-500 ml-1">*</span>
                      )}
                    </Label>
                    {renderField(field)}
                    {field.description && (
                      <p className="text-sm text-muted-foreground">
                        {field.description}
                      </p>
                    )}
                  </div>
                ))}
              </div>

              <div className="flex items-center justify-between pt-4 border-t">
                <div className="flex items-center gap-2">
                  <Label htmlFor="is_active">Active</Label>
                  <Switch
                    id="is_active"
                    checked={isActive}
                    onCheckedChange={setIsActive}
                  />
                </div>
                {optionalFields.length > 0 && (
                  <div className="flex items-center gap-2">
                    <Label htmlFor="show_advanced">Advanced</Label>
                    <Switch
                      id="show_advanced"
                      checked={showAdvanced}
                      onCheckedChange={setShowAdvanced}
                    />
                  </div>
                )}
              </div>

              {showAdvanced && (
                <div className="space-y-4">
                  {optionalFields.map((field) => (
                    <div key={field.name} className="space-y-2">
                      <Label htmlFor={field.name}>{field.label}</Label>
                      {renderField(field)}
                      {field.description && (
                        <p className="text-sm text-muted-foreground">
                          {field.description}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          <DialogFooter>
            <Button type="submit" disabled={isSubmitting} className="w-full">
              {isSubmitting && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              {mode === "create" ? "Create" : "Update"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
