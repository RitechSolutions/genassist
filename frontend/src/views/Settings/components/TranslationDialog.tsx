import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "react-hot-toast";
import { FormField } from "@/components/ui/form-field";
import { CRUDDialog } from "@/components/ui/crud-dialog";
import {
  createTranslation,
  updateTranslation,
  getTranslationByKey,
  getLanguages,
} from "@/services/translations";
import { Language, Translation } from "@/interfaces/translation.interface";

interface TranslationRow {
  /** Stable identity so React keys by row, not array index (Radix Select
   * desyncs when rows shift on deletion — see handleRemoveRow). */
  id: string;
  langCode: string;
  value: string;
}

let rowIdSeq = 0;
const nextRowId = () => `trow-${rowIdSeq++}`;

function translationsToRows(
  translations: Record<string, string>
): TranslationRow[] {
  return Object.entries(translations).map(([langCode, value]) => ({
    id: nextRowId(),
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

/**
 * CRUDDialog owns the top-level scalar `key` field; the dynamic per-language
 * translation rows (and their default selection) are managed as component-body
 * state and rendered through the render prop (see rule 13 of the migration).
 */
type TranslationFormValues = {
  key: string;
};

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
  // The dialog's effective mode can differ from the `mode` prop: when an
  // `initialKey` already exists, it flips to "edit" after the async lookup.
  const [dialogMode, setDialogMode] = useState<"create" | "edit">(mode);
  // Seed for the CRUDDialog-owned `key` field (props/async decide it).
  const [resolvedKey, setResolvedKey] = useState("");
  const [defaultLangCode, setDefaultLangCode] = useState<string | null>(null);
  const [rows, setRows] = useState<TranslationRow[]>([]);
  const [originalLangCodes, setOriginalLangCodes] = useState<string[]>([]);
  const [fetchedLanguages, setFetchedLanguages] = useState<Language[]>([]);

  const languages =
    languagesFromParent !== undefined ? languagesFromParent : fetchedLanguages;

  useEffect(() => {
    if (languagesFromParent !== undefined) return;
    getLanguages()
      .then(setFetchedLanguages)
      .catch(() => toast.error("Failed to load languages."));
  }, [languagesFromParent]);

  const languagesRef = useRef(languages);
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
      if (translationToEdit && mode === "edit") {
        setDialogMode("edit");
        setResolvedKey(translationToEdit.key || "");
        const builtRows = translationsToRows(translationToEdit.translations);
        setRows(builtRows);
        setOriginalLangCodes(builtRows.map((r) => r.langCode));
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
          setResolvedKey(existing.key || "");
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
          setOriginalLangCodes(builtRows.map((r) => r.langCode));
          setDefaultLangCode(defaultLang);
        } else {
          setDialogMode("create");
          setResolvedKey(initialKey);
          setOriginalLangCodes([]);
          const firstLang =
            langs.find((l) => l.code === "en")?.code ?? langs[0]?.code ?? "en";
          setRows(
            initialDefaultValue
              ? [
                  {
                    id: nextRowId(),
                    langCode: firstLang,
                    value: initialDefaultValue,
                  },
                ]
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
    setResolvedKey("");
    setDefaultLangCode(null);
    setRows([]);
    setOriginalLangCodes([]);
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
    setRows((prev) => [
      ...prev,
      { id: nextRowId(), langCode: newCode, value: "" },
    ]);
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

  return (
    <CRUDDialog<TranslationFormValues>
      open={isOpen}
      onOpenChange={onOpenChange}
      mode={dialogMode}
      maxWidth="860px"
      resetKey={`${dialogMode}:${resolvedKey}`}
      initialValues={{ key: resolvedKey }}
      title={{ create: "Add Translation", edit: "Edit Translation" }}
      submitLabel={{ create: "Create", edit: "Update" }}
      loadingLabel={{ create: "Creating...", edit: "Updating..." }}
      successMessage={{
        create: "Translation created successfully.",
        edit: "Translation updated successfully.",
      }}
      errorMessage="Failed to save translation."
      errorDisplay="both"
      validate={(values) => {
        if (!values.key.trim()) return { key: "Key is required" };
        const hasTranslation = rows.some(
          (r) => r.langCode && r.value.trim().length > 0
        );
        if (!hasTranslation) {
          return { key: "At least one translation is required" };
        }
        return null;
      }}
      onSubmit={async (values, { mode: m }) => {
        const cleanTranslations: Record<string, string> = {};
        for (const row of rows) {
          const trimmed = row.value.trim();
          if (trimmed && row.langCode) {
            cleanTranslations[row.langCode] = trimmed;
          }
        }

        if (m === "edit") {
          for (const code of originalLangCodes) {
            if (!(code in cleanTranslations)) {
              cleanTranslations[code] = "";
            }
          }
        }

        const defaultRow = rows.find((r) => r.langCode === defaultLangCode);
        const defaultValue = defaultRow?.value.trim() || null;

        if (m === "create") {
          const saved = await createTranslation({
            key: values.key.trim(),
            default: defaultValue,
            translations: cleanTranslations,
          });
          onTranslationSaved(saved);
        } else {
          const updateKey = translationToEdit?.key || values.key.trim();
          if (!updateKey) {
            throw new Error("Translation key is missing for update");
          }
          const saved = await updateTranslation(updateKey, {
            default: defaultValue,
            translations: cleanTranslations,
          });
          onTranslationSaved(saved);
        }
      }}
    >
      {({ values, setField, errors, mode: m }) => (
        <>
          {/* Validation errors ("Key is required" / "At least one translation
              is required") surfaced in one top-level inline div, matching the
              original single error banner. */}
          {errors.key ? (
            <div className="text-sm font-medium text-red-500">
              {errors.key}
            </div>
          ) : null}

          <FormField id="translation-key" label="Key">
            <Input
              id="translation-key"
              value={values.key}
              onChange={(e) => setField("key", e.target.value)}
              placeholder="translation.key"
              disabled={m === "edit" || !!initialKey}
              autoFocus
            />
          </FormField>

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
              <div key={row.id} className="flex items-start gap-2">
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
        </>
      )}
    </CRUDDialog>
  );
}
