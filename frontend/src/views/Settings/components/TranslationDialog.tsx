import React, { useCallback, useEffect, useMemo, useState } from "react";
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
import { SimpleTextarea as Textarea } from "@/components/ui/simpleTextarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Loader2, Plus, Trash2 } from "lucide-react";
import { toast } from "react-hot-toast";
import {
  createTranslation,
  updateTranslation,
  getTranslationByKey,
  getLanguages,
} from "@/services/translations";
import { Language, Translation } from "@/interfaces/translation.interface";

interface TranslationRow {
  langCode: string;
  value: string;
}

function translationsToRows(
  translations: Record<string, string>
): TranslationRow[] {
  return Object.entries(translations).map(([langCode, value]) => ({
    langCode,
    value,
  }));
}

function findDefaultLangCode(
  defaultValue: string | null | undefined,
  rows: TranslationRow[]
): string | null {
  if (!defaultValue) return null;
  const match = rows.find((r) => r.value === defaultValue);
  return match?.langCode ?? null;
}

interface TranslationDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onTranslationSaved: (translation: Translation) => void;
  translationToEdit?: Translation | null;
  mode?: "create" | "edit";
  initialKey?: string;
  initialDefaultValue?: string;
  /** When provided, the dialog does not fetch languages (caller loads once). */
  languages?: Language[];
}

export function TranslationDialog({
  isOpen,
  onOpenChange,
  onTranslationSaved,
  translationToEdit = null,
  mode = "create",
  initialKey,
  initialDefaultValue,
  languages: languagesFromParent,
}: TranslationDialogProps) {
  const [dialogMode, setDialogMode] = useState<"create" | "edit">(mode);
  const [key, setKey] = useState("");
  const [defaultLangCode, setDefaultLangCode] = useState<string | null>(null);
  const [rows, setRows] = useState<TranslationRow[]>([]);
  const [fetchedLanguages, setFetchedLanguages] = useState<Language[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  const languages =
    languagesFromParent !== undefined ? languagesFromParent : fetchedLanguages;

  useEffect(() => {
    if (languagesFromParent !== undefined) return;
    getLanguages()
      .then(setFetchedLanguages)
      .catch(() => toast.error("Failed to load languages."));
  }, [languagesFromParent]);

  const languagesRef = React.useRef(languages);
  languagesRef.current = languages;

  useEffect(() => {
    if (!isOpen) return;

    // Caller-provided language list: wait until loaded so the default lang row
    // matches the real catalog (parent input value seeds the correct language).
    if (
      languagesFromParent !== undefined &&
      languagesFromParent.length === 0
    ) {
      return;
    }

    let cancelled = false;
    const init = async () => {
      setError("");

      if (translationToEdit && mode === "edit") {
        setDialogMode("edit");
        setKey(translationToEdit.key || "");
        const builtRows = translationsToRows(translationToEdit.translations);
        setRows(builtRows);
        setDefaultLangCode(
          findDefaultLangCode(translationToEdit.default, builtRows)
        );
        return;
      }

      if (initialKey) {
        const existing = await getTranslationByKey(initialKey);
        if (cancelled) return;

        const langs = languagesRef.current;

        if (existing) {
          setDialogMode("edit");
          setKey(existing.key || "");
          const builtRows = translationsToRows(existing.translations);
          let defaultLang = findDefaultLangCode(existing.default, builtRows);
          if (defaultLang === null && builtRows.length > 0) {
            defaultLang =
              builtRows.find((r) => r.langCode === "en")?.langCode ??
              builtRows[0]?.langCode ??
              null;
          }
          let rowsToSet = builtRows;
          if (initialDefaultValue !== undefined && defaultLang) {
            rowsToSet = builtRows.map((r) =>
              r.langCode === defaultLang
                ? { ...r, value: initialDefaultValue }
                : r
            );
          }
          setRows(rowsToSet);
          setDefaultLangCode(defaultLang);
        } else {
          setDialogMode("create");
          setKey(initialKey);
          const firstLang =
            langs.find((l) => l.code === "en")?.code ??
            langs[0]?.code ??
            "en";
          setRows(
            initialDefaultValue
              ? [{ langCode: firstLang, value: initialDefaultValue }]
              : []
          );
          setDefaultLangCode(initialDefaultValue ? firstLang : null);
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
  }, [
    isOpen,
    translationToEdit,
    mode,
    initialKey,
    initialDefaultValue,
    languagesFromParent,
    languages,
  ]);

  const resetForm = () => {
    setKey("");
    setDefaultLangCode(null);
    setRows([]);
  };

  const usedCodes = useMemo(
    () => new Set(rows.map((r) => r.langCode)),
    [rows]
  );

  const availableLanguages = useMemo(
    () => languages.filter((l) => !usedCodes.has(l.code)),
    [languages, usedCodes]
  );

  const availableByRow = useMemo(
    () =>
      rows.map((row) =>
        languages.filter(
          (l) => l.code === row.langCode || !usedCodes.has(l.code)
        )
      ),
    [rows, languages, usedCodes]
  );

  const canAddRow = availableLanguages.length > 0;

  const handleAddRow = useCallback(() => {
    if (availableLanguages.length === 0) return;
    const newCode = availableLanguages[0].code;
    setRows((prev) => [...prev, { langCode: newCode, value: "" }]);
    setDefaultLangCode((prev) => prev ?? newCode);
  }, [availableLanguages]);

  const handleRemoveRow = useCallback(
    (index: number) => {
      const removedCode = rows[index]?.langCode;
      setRows((prev) => prev.filter((_, i) => i !== index));
      if (defaultLangCode === removedCode) {
        setDefaultLangCode(null);
      }
    },
    [rows, defaultLangCode]
  );

  const handleLangChange = useCallback(
    (index: number, newCode: string) => {
      const oldCode = rows[index]?.langCode;
      setRows((prev) =>
        prev.map((r, i) => (i === index ? { ...r, langCode: newCode } : r))
      );
      if (defaultLangCode === oldCode) {
        setDefaultLangCode(newCode);
      }
    },
    [rows, defaultLangCode]
  );

  const handleValueChange = useCallback((index: number, value: string) => {
    setRows((prev) =>
      prev.map((r, i) => (i === index ? { ...r, value } : r))
    );
  }, []);

  const title =
    dialogMode === "create" ? "Add Translation" : "Edit Translation";
  const submitLabel = dialogMode === "create" ? "Create" : "Update";
  const loadingLabel = dialogMode === "create" ? "Creating..." : "Updating...";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    e.stopPropagation();

    setError("");

    if (!key.trim()) {
      setError("Key is required");
      return;
    }

    const hasTranslation = rows.some(
      (r) => r.langCode && r.value.trim().length > 0
    );
    if (!hasTranslation) {
      setError("At least one translation is required");
      return;
    }

    try {
      setIsSubmitting(true);

      const cleanTranslations: Record<string, string> = {};
      for (const row of rows) {
        const trimmed = row.value.trim();
        if (trimmed && row.langCode) {
          cleanTranslations[row.langCode] = trimmed;
        }
      }

      const defaultRow = rows.find((r) => r.langCode === defaultLangCode);
      const defaultValue = defaultRow?.value.trim() || null;

      let saved: Translation;
      if (dialogMode === "create") {
        saved = await createTranslation({
          key: key.trim(),
          default: defaultValue,
          translations: cleanTranslations,
        });
        toast.success("Translation created successfully.");
      } else {
        const updateKey = translationToEdit?.key || key.trim();
        if (!updateKey) {
          setError("Translation key is missing for update");
          return;
        }

        saved = await updateTranslation(updateKey, {
          default: defaultValue,
          translations: cleanTranslations,
        });
        toast.success("Translation updated successfully.");
      }

      onTranslationSaved(saved);
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
      <DialogContent className="sm:max-w-[860px] p-0 overflow-hidden">
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

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label>Translations</Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleAddRow}
                  disabled={!canAddRow}
                  className="flex items-center gap-1"
                >
                  <Plus className="h-3.5 w-3.5" />
                  Add Translation
                </Button>
              </div>

              {rows.length > 0 && (
                <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                  <span className="w-[50px] shrink-0 text-center">Default</span>
                  <span className="w-[160px] shrink-0">Language</span>
                  <span className="flex-1">Value</span>
                  <span className="w-9 shrink-0" />
                </div>
              )}

              {rows.map((row, index) => (
                <div key={index} className="flex items-start gap-2">
                  <input
                    type="radio"
                    name="default-lang"
                    checked={defaultLangCode === row.langCode}
                    onChange={() => setDefaultLangCode(row.langCode)}
                    title="Set as default"
                    className="mt-3 w-[50px] shrink-0 cursor-pointer accent-primary"
                  />
                  <Select
                    value={row.langCode}
                    onValueChange={(val) => handleLangChange(index, val)}
                  >
                    <SelectTrigger className="w-[160px] shrink-0 rounded-md">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {(availableByRow[index] ?? []).map((lang) => (
                        <SelectItem key={lang.code} value={lang.code}>
                          {lang.name} ({lang.code})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Textarea
                    value={row.value}
                    onChange={(e) => handleValueChange(index, e.target.value)}
                    placeholder="Translation value"
                    rows={1}
                    className="flex-1 min-h-[40px]"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => handleRemoveRow(index)}
                    className="shrink-0 mt-0.5"
                  >
                    <Trash2 className="h-4 w-4 text-red-500" />
                  </Button>
                </div>
              ))}

              {rows.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  No translations added yet. Click "Add Translation" to start.
                </p>
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
