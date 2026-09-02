import React, {
  ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Button } from "@/components/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/tabs";
import { cn } from "@/helpers/utils";
import { extractErrorMessage } from "@/helpers/apiError";
import { Loader2 } from "lucide-react";
import { toast } from "react-hot-toast";

/**
 * <CRUDDialog<T>> — a reusable, generic create/edit dialog.
 *
 * Centralizes the boilerplate that is duplicated across every entity dialog in
 * the app (UserTypeDialog, LanguageDialog, RoleDialog, …):
 *   - form value lifecycle (populate on open, reset on close)
 *   - create vs. edit mode (titles, labels, initial values)
 *   - submit handling (preventDefault, validation gate, loading state)
 *   - error handling (API error extraction + toast/inline surfacing)
 *   - the standard Cancel / Save footer with a spinner
 *
 * The dialog owns the form-values object (`T`) and hands it to `children` via a
 * render prop, so consumers only describe their fields — not the plumbing.
 *
 * @example
 * ```tsx
 * type Values = { name: string };
 *
 * <CRUDDialog<Values>
 *   open={isOpen}
 *   onOpenChange={setIsOpen}
 *   mode={mode}
 *   initialValues={{ name: "" }}
 *   editValues={userTypeToEdit ? { name: userTypeToEdit.name } : null}
 *   title={{ create: "Create New User Type", edit: "Edit User Type" }}
 *   submitLabel={{ create: "Create User Type", edit: "Update User Type" }}
 *   loadingLabel={{ create: "Creating...", edit: "Updating..." }}
 *   validate={(v) => (!v.name.trim() ? { name: "Name is required" } : null)}
 *   successMessage={{ create: "User type created.", edit: "User type updated." }}
 *   onSubmit={async (v, { mode }) => {
 *     if (mode === "create") await createUserType(v);
 *     else await updateUserType(id, v);
 *   }}
 *   onSuccess={() => refetch()}
 * >
 *   {({ values, setField, errors }) => (
 *     <FormField label="Name" error={errors.name}>
 *       <Input value={values.name} onChange={(e) => setField("name", e.target.value)} />
 *     </FormField>
 *   )}
 * </CRUDDialog>
 * ```
 */

export type CRUDDialogMode = "create" | "edit";

/** A label that can differ between create and edit modes. */
export type ModeText = string | Record<CRUDDialogMode, string>;

/** Per-field validation errors, keyed by form-values field name. */
export type FieldErrors<T> = Partial<Record<keyof T, string | undefined>>;

/** The form controller handed to `children`, `footer`, and `submitDisabled`. */
export interface CRUDForm<T> {
  /** Current form values. */
  values: T;
  /** Whether the dialog is in create or edit mode. */
  mode: CRUDDialogMode;
  /** True while `onSubmit` is in flight. */
  isSubmitting: boolean;
  /** True when `values` differ from the values the form was initialized with. */
  isDirty: boolean;
  /** Current per-field validation errors. */
  errors: FieldErrors<T>;
  /** Form-level error from a failed submit (set when `errorDisplay` includes "inline"). */
  submitError: string | null;
  /** Replace all values, or update them with a functional updater. */
  setValues: (next: T | ((prev: T) => T)) => void;
  /** Update a single field (also clears that field's validation error). */
  setField: <K extends keyof T>(key: K, value: T[K]) => void;
  /** Set or clear a single field's validation error. */
  setFieldError: <K extends keyof T>(key: K, message: string | undefined) => void;
  /** Reset the form back to its initial values for the current mode. */
  reset: () => void;
  /** The currently selected tab value (only meaningful when `tabs` is set). */
  activeTab: string;
  /** Switch the active tab. */
  setActiveTab: (value: string) => void;
}

/** A tab shown in the dialog header when `tabs` is provided. */
export interface CRUDDialogTab {
  value: string;
  label: string;
}

export interface CRUDDialogProps<T extends Record<string, unknown>> {
  /** Whether the dialog is open. */
  open: boolean;
  /** Called when the dialog requests to open/close. */
  onOpenChange: (open: boolean) => void;
  /** Create or edit. Defaults to "create". */
  mode?: CRUDDialogMode;

  /** Baseline values used in create mode and as the reset baseline. */
  initialValues: T;
  /**
   * Values to populate when `mode === "edit"`. Merged over `initialValues`.
   * Pass `null`/`undefined` to fall back to `initialValues`.
   */
  editValues?: Partial<T> | null;
  /**
   * Optional token that re-initializes the form when it changes while open
   * (e.g. the edited entity's id). Use this when the entity being edited can
   * arrive or change asynchronously after the dialog is already open.
   */
  resetKey?: string | number | null;

  /** Dialog title. Defaults to "Create" / "Edit". */
  title?: ModeText;
  /** Optional dialog description under the title. */
  description?: ModeText;
  /** Submit button label. Defaults to "Create" / "Save Changes". */
  submitLabel?: ModeText;
  /** Cancel button label. Defaults to "Cancel". */
  cancelLabel?: string;
  /** Submit button label while submitting. Defaults to "Creating..." / "Saving...". */
  loadingLabel?: ModeText;

  /**
   * Synchronous validation run before submit. Return field errors to block the
   * submit, or `null`/`undefined`/empty to allow it.
   */
  validate?: (values: T) => FieldErrors<T> | null | undefined | void;
  /**
   * The async CRUD action. Throw to signal failure (the error is surfaced and
   * the dialog stays open). Do the API call + any cache invalidation here, or
   * put refetch/UI-sync in `onSuccess`.
   */
  onSubmit: (values: T, ctx: { mode: CRUDDialogMode }) => Promise<void> | void;
  /** Called after a successful submit (e.g. to refetch a list). */
  onSuccess?: (values: T, ctx: { mode: CRUDDialogMode }) => void;

  /**
   * Success toast message. String, per-mode map, or a builder. Pass `null` to
   * suppress the toast. Defaults to a generic per-mode message.
   */
  successMessage?: ModeText | ((values: T, mode: CRUDDialogMode) => string) | null;
  /**
   * Error message fallback. A string is used as the fallback when no message
   * can be extracted from the API error; a function fully overrides it.
   */
  errorMessage?: string | ((err: unknown, mode: CRUDDialogMode) => string);
  /** How submit errors are shown. Defaults to "toast". */
  errorDisplay?: "toast" | "inline" | "both";

  /** Close the dialog after a successful submit. Defaults to true. */
  closeOnSuccess?: boolean;
  /** Reset the form when the dialog closes. Defaults to true. */
  resetOnClose?: boolean;
  /** Block close requests while submitting. Defaults to true. */
  preventCloseWhileSubmitting?: boolean;
  /** Disable the submit button. Boolean or a predicate over the form controller. */
  submitDisabled?: boolean | ((form: CRUDForm<T>) => boolean);

  /**
   * When provided, a tab bar is rendered in the header (styled like the Agent
   * sheet). The active tab is exposed to `children` via `form.activeTab`; gate
   * your content on it (keep both panels mounted with a `hidden` class so field
   * state and validation survive tab switches). Pass `undefined` to hide the bar.
   */
  tabs?: CRUDDialogTab[];
  /** Initial/active-fallback tab value. Defaults to the first tab. */
  defaultTab?: string;

  /** Max width of the dialog content (CSS value). Defaults to "550px". */
  maxWidth?: string;
  /** Extra class names for the DialogContent. */
  contentClassName?: string;
  /** Extra class names for the scrollable body wrapper. */
  bodyClassName?: string;

  /** Content rendered on the left side of the footer (e.g. a delete button). */
  footerStart?: ReactNode | ((form: CRUDForm<T>) => ReactNode);
  /** Fully replace the footer. Receives the form controller. */
  footer?: ReactNode | ((form: CRUDForm<T>) => ReactNode);

  /** The form fields — a render prop bound to the form controller, or plain nodes. */
  children: ReactNode | ((form: CRUDForm<T>) => ReactNode);
}

const DEFAULT_TITLE: Record<CRUDDialogMode, string> = {
  create: "Create",
  edit: "Edit",
};
const DEFAULT_SUBMIT: Record<CRUDDialogMode, string> = {
  create: "Create",
  edit: "Save Changes",
};
const DEFAULT_LOADING: Record<CRUDDialogMode, string> = {
  create: "Creating...",
  edit: "Saving...",
};

function resolveText(
  text: ModeText | undefined,
  mode: CRUDDialogMode,
  fallback: Record<CRUDDialogMode, string>
): string {
  if (text == null) return fallback[mode];
  return typeof text === "string" ? text : text[mode];
}

function shallowEqual(
  a: Record<string, unknown>,
  b: Record<string, unknown>
): boolean {
  if (a === b) return true;
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  for (const key of keys) {
    if (a[key] !== b[key]) return false;
  }
  return true;
}

export function CRUDDialog<T extends Record<string, unknown>>({
  open,
  onOpenChange,
  mode = "create",
  initialValues,
  editValues,
  resetKey = null,
  title,
  description,
  submitLabel,
  cancelLabel = "Cancel",
  loadingLabel,
  validate,
  onSubmit,
  onSuccess,
  successMessage,
  errorMessage,
  errorDisplay = "toast",
  closeOnSuccess = true,
  resetOnClose = true,
  preventCloseWhileSubmitting = true,
  submitDisabled,
  tabs,
  defaultTab,
  maxWidth = "550px",
  contentClassName,
  bodyClassName,
  footerStart,
  footer,
  children,
}: CRUDDialogProps<T>) {
  // Read initial/edit values through refs so inline object props (which get a
  // fresh identity every render) don't re-trigger the initialization effect.
  const initialValuesRef = useRef(initialValues);
  initialValuesRef.current = initialValues;
  const editValuesRef = useRef(editValues);
  editValuesRef.current = editValues;

  const buildBaseline = useCallback((m: CRUDDialogMode): T => {
    const base = { ...initialValuesRef.current };
    if (m === "edit" && editValuesRef.current) {
      return { ...base, ...editValuesRef.current } as T;
    }
    return base as T;
  }, []);

  const defaultTabValue = defaultTab ?? tabs?.[0]?.value ?? "";

  const [values, setValuesState] = useState<T>(() => buildBaseline(mode));
  const [baseline, setBaseline] = useState<T>(() => buildBaseline(mode));
  const [errors, setErrors] = useState<FieldErrors<T>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeTabState, setActiveTab] = useState<string>(defaultTabValue);

  // The active tab, guarded so it always resolves to a real tab (e.g. when the
  // set of tabs changes or disappears while open).
  const activeTab =
    tabs && tabs.some((t) => t.value === activeTabState)
      ? activeTabState
      : defaultTabValue;

  // (Re)initialize when the dialog opens, the mode flips, or resetKey changes.
  useEffect(() => {
    if (!open) return;
    const next = buildBaseline(mode);
    setValuesState(next);
    setBaseline(next);
    setErrors({});
    setSubmitError(null);
    setIsSubmitting(false);
    setActiveTab(defaultTabValue);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, mode, resetKey]);

  // Clear leftover values/errors once the close animation is done.
  useEffect(() => {
    if (open || !resetOnClose) return;
    setErrors({});
    setSubmitError(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const setValues = useCallback((next: T | ((prev: T) => T)) => {
    setValuesState((prev) =>
      typeof next === "function" ? (next as (p: T) => T)(prev) : next
    );
  }, []);

  const setField = useCallback(<K extends keyof T>(key: K, value: T[K]) => {
    setValuesState((prev) => ({ ...prev, [key]: value }) as T);
    setErrors((prev) => (prev[key] ? { ...prev, [key]: undefined } : prev));
  }, []);

  const setFieldError = useCallback(
    <K extends keyof T>(key: K, message: string | undefined) => {
      setErrors((prev) => ({ ...prev, [key]: message }));
    },
    []
  );

  const reset = useCallback(() => {
    const next = buildBaseline(mode);
    setValuesState(next);
    setBaseline(next);
    setErrors({});
    setSubmitError(null);
  }, [buildBaseline, mode]);

  const handleOpenChange = useCallback(
    (next: boolean) => {
      if (!next && isSubmitting && preventCloseWhileSubmitting) return;
      onOpenChange(next);
    },
    [isSubmitting, preventCloseWhileSubmitting, onOpenChange]
  );

  const form: CRUDForm<T> = {
    values,
    mode,
    isSubmitting,
    isDirty: !shallowEqual(values, baseline),
    errors,
    submitError,
    setValues,
    setField,
    setFieldError,
    reset,
    activeTab,
    setActiveTab,
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);

    if (validate) {
      const result = validate(values) || {};
      const hasError = Object.values(result).some(Boolean);
      setErrors(result);
      if (hasError) return;
    } else {
      setErrors({});
    }

    try {
      setIsSubmitting(true);
      await onSubmit(values, { mode });

      if (successMessage !== null) {
        const msg =
          typeof successMessage === "function"
            ? successMessage(values, mode)
            : resolveText(successMessage, mode, {
                create: "Created successfully.",
                edit: "Saved successfully.",
              });
        if (msg) toast.success(msg);
      }

      onSuccess?.(values, { mode });

      if (closeOnSuccess) {
        onOpenChange(false);
      }
    } catch (err) {
      const msg =
        typeof errorMessage === "function"
          ? errorMessage(err, mode)
          : extractErrorMessage(
              err,
              errorMessage ??
                `Failed to ${mode === "create" ? "create" : "save"}. Please try again.`
            );
      if (errorDisplay === "toast" || errorDisplay === "both") toast.error(msg);
      if (errorDisplay === "inline" || errorDisplay === "both") setSubmitError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const isSubmitDisabled =
    isSubmitting ||
    (typeof submitDisabled === "function"
      ? submitDisabled(form)
      : Boolean(submitDisabled));

  const body = typeof children === "function" ? children(form) : children;
  const footerStartNode =
    typeof footerStart === "function" ? footerStart(form) : footerStart;

  const resolvedFooter =
    footer !== undefined ? (
      typeof footer === "function" ? (
        footer(form)
      ) : (
        footer
      )
    ) : (
      <div className="flex w-full items-center justify-between gap-3">
        <div className="flex items-center gap-2">{footerStartNode}</div>
        <div className="flex justify-end gap-3">
          <Button
            type="button"
            variant="outline"
            className="px-4"
            onClick={() => handleOpenChange(false)}
            disabled={isSubmitting}
          >
            {cancelLabel}
          </Button>
          <Button type="submit" className="px-4" disabled={isSubmitDisabled}>
            {isSubmitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {resolveText(loadingLabel, mode, DEFAULT_LOADING)}
              </>
            ) : (
              resolveText(submitLabel, mode, DEFAULT_SUBMIT)
            )}
          </Button>
        </div>
      </div>
    );

  const resolvedDescription = description
    ? resolveText(description, mode, { create: "", edit: "" })
    : "";

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        className={cn("p-0 overflow-hidden", contentClassName)}
        style={{ maxWidth }}
      >
        <form onSubmit={handleSubmit} className="flex max-h-[90vh] flex-col">
          <DialogHeader className="p-6 pb-4">
            <DialogTitle className="text-xl">
              {resolveText(title, mode, DEFAULT_TITLE)}
            </DialogTitle>
            {resolvedDescription ? (
              <DialogDescription>{resolvedDescription}</DialogDescription>
            ) : null}
            {tabs && tabs.length > 0 ? (
              <Tabs
                value={activeTab}
                onValueChange={setActiveTab}
                className="mt-3"
              >
                <TabsList className="h-9">
                  {tabs.map((t) => (
                    <TabsTrigger key={t.value} value={t.value} type="button">
                      {t.label}
                    </TabsTrigger>
                  ))}
                </TabsList>
              </Tabs>
            ) : null}
          </DialogHeader>

          <div
            className={cn(
              "px-6 pb-6 space-y-5 overflow-y-auto overflow-x-hidden",
              bodyClassName
            )}
          >
            {(errorDisplay === "inline" || errorDisplay === "both") &&
            submitError ? (
              <div className="text-sm font-medium text-red-500">
                {submitError}
              </div>
            ) : null}
            {body}
          </div>

          <DialogFooter className="border-t px-6 py-4">
            {resolvedFooter}
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default CRUDDialog;
