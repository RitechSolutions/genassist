import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Textarea } from "@/components/textarea";
import { Loader2 } from "lucide-react";
import { toast } from "react-hot-toast";
import {
  createTranslation,
  updateTranslation,
  getTranslationByKey,
  getLanguages,
} from "@/services/translations";
import { Language, Translation } from "@/interfaces/translation.interface";

interface TranslationDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onTranslationSaved: () => void;
  translationToEdit?: Translation | null;
  mode?: "create" | "edit";
  /** Optional initial key to load or prefill (used for inline field translations) */
  initialKey?: string;
  /** Optional initial default value when creating a new translation for a field */
  initialDefaultValue?: string;
}

export function TranslationDialog({
  isOpen,
  onOpenChange,
  onTranslationSaved,
  translationToEdit = null,
  mode = "create",
  initialKey,
  initialDefaultValue,
}: TranslationDialogProps) {
  const [dialogMode, setDialogMode] = useState<"create" | "edit">(mode);
  const [key, setKey] = useState("");
  const [defaultValue, setDefaultValue] = useState("");
  const [translations, setTranslations] = useState<Record<string, string>>({});
  const [languages, setLanguages] = useState<Language[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getLanguages().then(setLanguages).catch(() => {});
  }, []);

  useEffect(() => {
    setDialogMode(mode);
  }, [mode]);

  useEffect(() => {
    if (!isOpen) return;

    let cancelled = false;
    const init = async () => {
      setError("");

      if (translationToEdit && mode === "edit") {
        setDialogMode("edit");
        setKey(translationToEdit.key || "");
        setDefaultValue(translationToEdit.default || "");
        setTranslations({ ...translationToEdit.translations });
        return;
      }

      if (initialKey) {
        const existing = await getTranslationByKey(initialKey);
        if (cancelled) return;

        if (existing) {
          setDialogMode("edit");
          setKey(existing.key || "");
          setDefaultValue(existing.default || "");
          setTranslations({ ...existing.translations });
        } else {
          setDialogMode("create");
          setKey(initialKey);
          setDefaultValue(initialDefaultValue || "");
          setTranslations({});
        }
        return;
      }

      setDialogMode("create");
      resetForm();
    };

    void init();

    return () => {
      cancelled = true;
    };
  }, [isOpen, translationToEdit, mode, initialKey, initialDefaultValue]);

  const resetForm = () => {
    setKey("");
    setDefaultValue("");
    setTranslations({});
  };

  const title =
    dialogMode === "create" ? "Add Translation" : "Edit Translation";
  const submitLabel = dialogMode === "create" ? "Create" : "Update";
  const loadingLabel = dialogMode === "create" ? "Creating..." : "Updating...";

  const handleTranslationChange = (code: string, value: string) => {
    setTranslations((prev) => ({ ...prev, [code]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!key.trim()) {
      setError("Key is required");
      return;
    }

    try {
      setIsSubmitting(true);

      // Build translations dict, omitting empty values
      const cleanTranslations: Record<string, string> = {};
      for (const [code, value] of Object.entries(translations)) {
        const trimmed = value.trim();
        if (trimmed) {
          cleanTranslations[code] = trimmed;
        }
      }

      if (dialogMode === "create") {
        await createTranslation({
          key: key.trim(),
          default: defaultValue.trim() || null,
          translations: cleanTranslations,
        });
        toast.success("Translation created successfully.");
      } else {
        const updateKey = translationToEdit?.key || key.trim();
        if (!updateKey) {
          setError("Translation key is missing for update");
          return;
        }

        await updateTranslation(updateKey, {
          default: defaultValue.trim() || null,
          translations: cleanTranslations,
        });
        toast.success("Translation updated successfully.");
      }

      onTranslationSaved();
      onOpenChange(false);
      resetForm();
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Failed to save translation.";
      setError(msg);
      toast.error(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] p-0 overflow-hidden">
        <form onSubmit={handleSubmit} className="max-h-[90vh] flex flex-col">
          <DialogHeader className="p-6 pb-4">
            <DialogTitle className="text-xl">{title}</DialogTitle>
          </DialogHeader>

          <div className="px-6 pb-6 space-y-4 overflow-y-auto">
            {error && (
              <div className="text-sm font-medium text-red-500">{error}</div>
            )}

            <div className="grid gap-2">
              <Label htmlFor="translation-key">Key</Label>
              <Input
                id="translation-key"
                value={key}
                onChange={(e) => setKey(e.target.value)}
                placeholder="translation.key"
                disabled={dialogMode === "edit" || !!initialKey}
                autoFocus
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="translation-default">Default</Label>
              <Textarea
                id="translation-default"
                value={defaultValue}
                onChange={(e) => setDefaultValue(e.target.value)}
                placeholder="Default fallback value"
                rows={2}
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {languages.map((lang) => (
                <div key={lang.id} className="grid gap-2">
                  <Label htmlFor={`translation-${lang.code}`}>
                    {lang.name} ({lang.code})
                  </Label>
                  <Textarea
                    id={`translation-${lang.code}`}
                    value={translations[lang.code] || ""}
                    onChange={(e) =>
                      handleTranslationChange(lang.code, e.target.value)
                    }
                    rows={2}
                  />
                </div>
              ))}
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
                    {loadingLabel}
                  </>
                ) : (
                  submitLabel
                )}
              </Button>
            </div>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
