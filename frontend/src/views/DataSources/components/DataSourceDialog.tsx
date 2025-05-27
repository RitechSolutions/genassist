import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/dialog";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { createDataSource, updateDataSource } from "@/services/dataSources";
import { Switch } from "@/components/switch";
import { Label } from "@/components/label";
import { toast } from "react-hot-toast";
import { Loader2 } from "lucide-react";
import { DataSource } from "@/interfaces/dataSource.interface";

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
  const [source_type, setSource_type] = useState("");
  const [connection_data, setConnectionData] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [dataSourceId, setDataSourceId] = useState<string | undefined>("");

  useEffect(() => {
    if (isOpen) {
      resetForm();
      if (dataSourceToEdit && mode === "edit") {
        populateFormWithDataSource(dataSourceToEdit);
      }
    }
  }, [isOpen, dataSourceToEdit, mode]);

  const populateFormWithDataSource = (dataSource: DataSource) => {
    setDataSourceId(dataSource.id);
    setName(dataSource.name);
    setSource_type(dataSource.source_type);
    setConnectionData(dataSource.connection_data);
    setIsActive(dataSource.is_active === 1);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !source_type || !connection_data) {
      toast.error("All fields are required");
      return;
    }

    setIsSubmitting(true);
    try {
      const dataSourceData: Partial<DataSource> = {
        name,
        source_type,
        connection_data,
        is_active: isActive ? 1 : 0,
      };

      if (mode === "create") {
        await createDataSource(dataSourceData as DataSource);
        toast.success("Data Source created successfully");
      } else {
        if (!dataSourceId) {
          toast.error("Data Source ID is missing for update");
          return;
        }
        await updateDataSource(dataSourceId, dataSourceData);
        toast.success("Data Source updated successfully");
      }

      onDataSourceSaved();
      onOpenChange(false);
      resetForm();
    } catch (error) {
      toast.error(`Failed to ${mode} data source`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const resetForm = () => {
    setDataSourceId(undefined);
    setName("");
    setSource_type("");
    setConnectionData("");
    setIsActive(true);
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
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
            <Input
              id="source_type"
              value={source_type}
              onChange={(e) => setSource_type(e.target.value)}
              placeholder="Source Type"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="connection_data">Connection Data</Label>
            <Input
              id="connection_data"
              value={connection_data}
              onChange={(e) => setConnectionData(e.target.value)}
              placeholder="Connection Data"
            />
          </div>
          <div className="flex items-center gap-2">
            <Label htmlFor="is_active">Active</Label>
            <Switch
              id="is_active"
              checked={isActive}
              onCheckedChange={setIsActive}
            />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={isSubmitting} className="w-full">
              {isSubmitting ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              {mode === "create" ? "Create" : "Update"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}