import { useEffect, useState } from "react";
import { Language } from "@/interfaces/translation.interface";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Button } from "@/components/button";
import { SimpleInput as Input } from "@/components/ui/simpleInput";
import { Label } from "@/components/label";
import { Switch } from "@/components/switch";
import { createLanguage, updateLanguage } from "@/services/translations";
import { Loader2 } from "lucide-react";
import { toast } from "react-hot-toast";

interface LanguageDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onLanguageSaved: () => void;
  languageToEdit?: Language | null;
  mode?: "create" | "edit";
}

export function LanguageDialog({
  isOpen,
  onOpenChange,
  onLanguageSaved,
  languageToEdit = null,
  mode = "create",
}: LanguageDialogProps) {
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [languageId, setLanguageId] = useState<string | undefined>(undefined);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">(mode);
  const [error, setError] = useState("");

  const title = dialogMode === "create" ? "Add New Language" : "Edit Language";
  const submitButtonText =
    dialogMode === "create" ? "Create Language" : "Update Language";
  const loadingText = dialogMode === "create" ? "Creating..." : "Updating...";

  useEffect(() => {
    setDialogMode(mode);
  }, [mode]);

  useEffect(() => {
    if (isOpen) {
      resetForm();
      setError("");

      if (languageToEdit && dialogMode === "edit") {
        populateFormWithLanguageData(languageToEdit);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, languageToEdit, dialogMode]);

  const populateFormWithLanguageData = (language: Language) => {
    setLanguageId(language.id);
    setCode(language.code || "");
    setName(language.name || "");
    setIsActive(language.is_active);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!code.trim()) {
      setError("Language code is required");
      return;
    }

    if (!name.trim()) {
      setError("Language name is required");
      return;
    }

    try {
      setIsSubmitting(true);

      if (dialogMode === "create") {
        await createLanguage({ code: code.trim().toLowerCase(), name: name.trim() });
        toast.success("Language created successfully.");
      } else {
        if (!languageId) {
          setError("Language ID is missing for update");
          return;
        }
        await updateLanguage(languageId, { name: name.trim(), is_active: isActive });
        toast.success("Language updated successfully.");
      }

      onLanguageSaved();
      onOpenChange(false);
      resetForm();
    } catch (err) {
      const errorMessage =
        err instanceof Error
          ? err.message
          : `Failed to ${dialogMode} language`;
      setError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  const resetForm = () => {
    if (dialogMode === "create") {
      setLanguageId(undefined);
      setCode("");
      setName("");
      setIsActive(true);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[450px] p-0 overflow-hidden">
        <form onSubmit={handleSubmit}>
          <DialogHeader className="p-6 pb-4">
            <DialogTitle className="text-xl">{title}</DialogTitle>
          </DialogHeader>

          <div className="px-6 pb-6">
            <div className="grid gap-4 py-4">
              {error && (
                <div className="text-sm font-medium text-red-500">{error}</div>
              )}

              <div className="grid gap-2">
                <Label htmlFor="code">Code</Label>
                <Input
                  id="code"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="en, fr, de, it..."
                  disabled={dialogMode === "edit"}
                  autoFocus={dialogMode === "create"}
                  maxLength={10}
                />
                {dialogMode === "edit" && (
                  <p className="text-xs text-muted-foreground">
                    Language code cannot be changed after creation
                  </p>
                )}
              </div>

              <div className="grid gap-2">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="English, French, German..."
                  autoFocus={dialogMode === "edit"}
                />
              </div>

              {dialogMode === "edit" && (
                <div className="flex items-center justify-between">
                  <Label htmlFor="is_active" className="cursor-pointer">
                    Active
                  </Label>
                  <Switch
                    id="is_active"
                    checked={isActive}
                    onCheckedChange={setIsActive}
                  />
                </div>
              )}
            </div>
          </div>

          <DialogFooter className="px-6 py-4 border-t">
            <div className="flex justify-end gap-3 w-full">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {loadingText}
                  </>
                ) : (
                  submitButtonText
                )}
              </Button>
            </div>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
