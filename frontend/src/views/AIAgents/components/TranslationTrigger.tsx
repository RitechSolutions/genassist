import React, { useEffect, useState } from "react";
import { Languages } from "lucide-react";
import { TranslationDialog } from "@/views/Settings/components/TranslationDialog";
import { getTranslationByKey } from "@/services/translations";
import { Language, Translation } from "@/interfaces/translation.interface";
import { getTranslationCount } from "../utils";

interface TranslationTriggerProps {
  /** Dotted translation key, e.g. `agent.{id}.node.{nodeId}.fields.{name}.label`. */
  translationKey: string;
  /** The current source (default-language) value for this key. */
  currentValue: string;
  /** Optional short caption shown next to the icon (useful when triggers are grouped). */
  label?: string;
  /** Shared list so each dialog does not re-fetch languages. Omit to let the dialog fetch. */
  languages?: Language[];
  /** Sync the parent field to the saved translation default. */
  onTranslationDefaultSaved?: (defaultText: string) => void;
}

/**
 * Reusable "manage translations" button + dialog for a single translation key. Mirrors the
 * per-field trigger used in AgentForm so node content (e.g. Human In The Loop form labels)
 * gets the exact same translation UX. Renders the shared TranslationDialog unchanged.
 */
export const TranslationTrigger: React.FC<TranslationTriggerProps> = ({
  translationKey,
  currentValue,
  label,
  languages,
  onTranslationDefaultSaved,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [refreshCounter, setRefreshCounter] = useState(0);
  const [translationCount, setTranslationCount] = useState(0);

  useEffect(() => {
    let cancelled = false;

    const loadTranslationCount = async () => {
      if (!translationKey) {
        setTranslationCount(0);
        return;
      }

      const translation = await getTranslationByKey(translationKey);
      if (cancelled) return;

      setTranslationCount(getTranslationCount(translation));
    };

    void loadTranslationCount();

    return () => {
      cancelled = true;
    };
  }, [translationKey, refreshCounter]);

  const handleSaved = (translation: Translation) => {
    setRefreshCounter((prev) => prev + 1);
    onTranslationDefaultSaved?.(translation.default ?? "");
  };

  const hasTranslations = translationCount > 0;

  return (
    <>
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className={`inline-flex items-center gap-1.5 h-6 rounded-full border border-dashed px-2 transition-colors ${
          hasTranslations
            ? "border-primary text-primary"
            : "border-muted-foreground/40 text-muted-foreground hover:text-primary hover:border-primary"
        }`}
        title={
          hasTranslations
            ? `Manage translations (${translationCount})`
            : "Manage translations"
        }
      >
        <Languages className="h-3.5 w-3.5" />
        {label && <span className="text-xs leading-none">{label}</span>}
        {hasTranslations && (
          <span className="text-sm font-medium leading-none">
            {translationCount}
          </span>
        )}
      </button>
      {/* Keyed by translationKey and refreshCounter so the dialog re-initializes when needed */}
      <TranslationDialog
        key={`${translationKey}-${refreshCounter}`}
        isOpen={isOpen}
        onOpenChange={setIsOpen}
        mode="create"
        translationToEdit={null}
        initialKey={translationKey}
        initialDefaultValue={currentValue}
        onTranslationSaved={handleSaved}
        // Pass the shared list when available; otherwise let the dialog fetch its own so
        // an empty/not-yet-loaded list never leaves the dialog without languages.
        languages={languages && languages.length ? languages : undefined}
      />
    </>
  );
};

export default TranslationTrigger;
