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
} from "@/services/translations";
import { Translation } from "@/interfaces/translation.interface";

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
  const [en, setEn] = useState("");
  const [es, setEs] = useState("");
  const [fr, setFr] = useState("");
  const [de, setDe] = useState("");
  const [pt, setPt] = useState("");
  const [zh, setZh] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setDialogMode(mode);
  }, [mode]);

  useEffect(() => {
    if (!isOpen) return;

    let cancelled = false;
    const init = async () => {
      setError("");

      // Explicit edit with provided translation object (used from Translations page)
      if (translationToEdit && mode === "edit") {
        setDialogMode("edit");
        setKey(translationToEdit.key || "");
        setDefaultValue(translationToEdit.default || "");
        setEn(translationToEdit.en || "");
        setEs(translationToEdit.es || "");
        setFr(translationToEdit.fr || "");
        setDe(translationToEdit.de || "");
        setPt(translationToEdit.pt || "");
        setZh(translationToEdit.zh || "");
        return;
      }

      // When an initial key is provided (e.g. inline translation from another form),
      // try to load existing translation by key; if none, prefill default value.
      if (initialKey) {
        const existing = await getTranslationByKey(initialKey);
        if (cancelled) return;

        if (existing) {
          setDialogMode("edit");
          setKey(existing.key || "");
          setDefaultValue(existing.default || "");
          setEn(existing.en || "");
          setEs(existing.es || "");
          setFr(existing.fr || "");
          setDe(existing.de || "");
          setPt(existing.pt || "");
          setZh(existing.zh || "");
        } else {
          setDialogMode("create");
          setKey(initialKey);
          setDefaultValue(initialDefaultValue || "");
          setEn("");
          setEs("");
          setFr("");
          setDe("");
          setPt("");
          setZh("");
        }
        return;
      }

      // Plain create mode (used from Translations list "Add" button)
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
    setEn("");
    setEs("");
    setFr("");
    setDe("");
    setPt("");
    setZh("");
  };

  const title =
    dialogMode === "create" ? "Add Translation" : "Edit Translation";
  const submitLabel = dialogMode === "create" ? "Create" : "Update";
  const loadingLabel = dialogMode === "create" ? "Creating..." : "Updating...";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!key.trim()) {
      setError("Key is required");
      return;
    }

    try {
      setIsSubmitting(true);

      if (dialogMode === "create") {
        await createTranslation({
          key: key.trim(),
          default: defaultValue.trim() || null,
          en: en.trim() || null,
          es: es.trim() || null,
          fr: fr.trim() || null,
          de: de.trim() || null,
          pt: pt.trim() || null,
          zh: zh.trim() || null,
        });
        toast.success("Translation created successfully.");
      } else {
        if (!translationToEdit) {
          setError("Translation is missing for update");
          return;
        }

        await updateTranslation(translationToEdit.key, {
          default: defaultValue.trim() || null,
          en: en.trim() || null,
          es: es.trim() || null,
          fr: fr.trim() || null,
          de: de.trim() || null,
          pt: pt.trim() || null,
          zh: zh.trim() || null,
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
                disabled={dialogMode === "edit"}
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
              <div className="grid gap-2">
                <Label htmlFor="translation-en">English (en)</Label>
                <Textarea
                  id="translation-en"
                  value={en}
                  onChange={(e) => setEn(e.target.value)}
                  rows={2}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="translation-es">Spanish (es)</Label>
                <Textarea
                  id="translation-es"
                  value={es}
                  onChange={(e) => setEs(e.target.value)}
                  rows={2}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="translation-fr">French (fr)</Label>
                <Textarea
                  id="translation-fr"
                  value={fr}
                  onChange={(e) => setFr(e.target.value)}
                  rows={2}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="translation-de">German (de)</Label>
                <Textarea
                  id="translation-de"
                  value={de}
                  onChange={(e) => setDe(e.target.value)}
                  rows={2}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="translation-pt">Portuguese (pt)</Label>
                <Textarea
                  id="translation-pt"
                  value={pt}
                  onChange={(e) => setPt(e.target.value)}
                  rows={2}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="translation-zh">Chinese (zh)</Label>
                <Textarea
                  id="translation-zh"
                  value={zh}
                  onChange={(e) => setZh(e.target.value)}
                  rows={2}
                />
              </div>
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

