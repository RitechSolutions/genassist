import { useEffect, useState } from "react";
import { FeatureFlag, FeatureFlagFormData } from "@/interfaces/featureFlag.interface";
import { toast } from "react-hot-toast";
import { FormDialog } from "@/components/ui/form-dialog";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Textarea } from "@/components/textarea";
import { Switch } from "@/components/switch";
import { createFeatureFlag, updateFeatureFlag } from "@/services/featureFlags";

interface FeatureFlagDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onFeatureFlagSaved: () => void;
  featureFlagToEdit?: FeatureFlag | null;
  mode?: 'create' | 'edit';
}

export function FeatureFlagDialog({
  isOpen,
  onOpenChange,
  onFeatureFlagSaved,
  featureFlagToEdit = null,
  mode = 'create'
}: FeatureFlagDialogProps) {
  const [key, setKey] = useState("");
  const [val, setVal] = useState("");
  const [description, setDescription] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [featureFlagId, setFeatureFlagId] = useState<string | undefined>(undefined);
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>(mode);
  const [error, setError] = useState("");

  const title = dialogMode === 'create' ? 'Create New Feature Flag' : 'Edit Feature Flag';
  const submitButtonText = dialogMode === 'create' ? 'Create Feature Flag' : 'Update Feature Flag';
  const loadingText = dialogMode === 'create' ? 'Creating...' : 'Updating...';

  useEffect(() => {
    setDialogMode(mode);
  }, [mode]);

  useEffect(() => {
    if (isOpen) {
      resetForm();
      setError("");
      
      if (featureFlagToEdit && dialogMode === 'edit') {
        populateFormWithFeatureFlagData(featureFlagToEdit);
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, featureFlagToEdit, dialogMode]);

  const populateFormWithFeatureFlagData = (flag: FeatureFlag) => {
    setFeatureFlagId(flag.id);
    setKey(flag.key || "");
    setVal(flag.val || "");
    setDescription(flag.description || "");
    setIsActive(flag.is_active === 1);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    
    if (!key.trim()) {
      setError("Feature flag key is required");
      return;
    }

    if (!val.trim()) {
      setError("Feature flag value is required");
      return;
    }

    try {
      setIsSubmitting(true);
      const flagData: FeatureFlagFormData = {
        key: key.trim(),
        val: val.trim(),
        description: description.trim(),
        is_active: isActive ? 1 : 0,
      };

      if (dialogMode === 'create') {
        await createFeatureFlag(flagData);
        toast.success("Feature flag created successfully");
      } else {
        if (!featureFlagId) {
          setError("Feature flag ID is missing for update");
          return;
        }
        
        flagData.id = featureFlagId;
        await updateFeatureFlag(featureFlagId, flagData);
        toast.success("Feature flag updated successfully");
      }

      onFeatureFlagSaved();
      onOpenChange(false);
      resetForm();
    } catch (err) {
      const errorMessage = err instanceof Error 
        ? err.message 
        : `Failed to ${dialogMode} feature flag`;
      setError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  const resetForm = () => {
    if (dialogMode === 'create') {
      setFeatureFlagId(undefined);
      setKey("");
      setVal("");
      setDescription("");
      setIsActive(true);
    }
  };

  return (
    <FormDialog
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      title={title}
      description="Enter the details for the feature flag"
      onSubmit={handleSubmit}
      isLoading={isSubmitting}
      submitButtonText={submitButtonText}
      loadingText={loadingText}
    >
      <div className="grid gap-4 py-4">
        {error && (
          <div className="text-sm font-medium text-red-500">
            {error}
          </div>
        )}
        
        <div className="grid gap-2">
          <Label htmlFor="key">Key</Label>
          <Input
            id="key"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="feature.name"
            autoFocus
          />
        </div>
        
        <div className="grid gap-2">
          <Label htmlFor="val">Value</Label>
          <Input
            id="val"
            value={val}
            onChange={(e) => setVal(e.target.value)}
            placeholder="true, false, or a variant value"
          />
        </div>
        
        <div className="grid gap-2">
          <Label htmlFor="description">Description</Label>
          <Textarea
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Description of what this feature flag controls"
          />
        </div>
        
        <div className="flex items-center justify-between">
          <Label htmlFor="is_active" className="cursor-pointer">Active</Label>
          <Switch
            id="is_active"
            checked={isActive}
            onCheckedChange={setIsActive}
          />
        </div>
      </div>
    </FormDialog>
  );
} 