import { Input } from "@/components/ui/input";
import { badgeVariants } from "@/components/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { FormField } from "@/components/ui/form-field";
import { CRUDDialog, type FieldErrors } from "@/components/ui/crud-dialog";
import { extractErrorMessage } from "@/helpers/apiError";
import { cn } from "@/helpers/utils";
import {
  createIssueStatus,
  IssueCategory,
  IssueStatus,
  updateIssueStatus,
} from "@/services/issueStatuses";
import {
  CATEGORY_META,
  STATUS_COLOR_CLASSES,
} from "@/views/ReportedFeedback/constants";
import {
  changedFields,
  DEFAULT_STATUS_KEY,
  issueStatusKeyError,
  IssueStatusFormValues,
} from "../helpers/issueStatusForm";

interface FeedbackStatusDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onStatusSaved: () => void;
  statusToEdit?: IssueStatus | null;
  mode?: "create" | "edit";
}

export function FeedbackStatusDialog({
  isOpen,
  onOpenChange,
  onStatusSaved,
  statusToEdit = null,
  mode = "create",
}: FeedbackStatusDialogProps) {
  const isDefault = mode === "edit" && statusToEdit?.key === DEFAULT_STATUS_KEY;

  return (
    <CRUDDialog<IssueStatusFormValues>
      open={isOpen}
      onOpenChange={onOpenChange}
      mode={mode}
      maxWidth="450px"
      resetKey={statusToEdit?.id ?? null}
      initialValues={{ key: "", label: "", category: "todo", color: "zinc" }}
      editValues={
        statusToEdit
          ? {
              key: statusToEdit.key,
              label: statusToEdit.label,
              category: statusToEdit.category,
              color: statusToEdit.color,
            }
          : null
      }
      title={{ create: "Add Status", edit: "Edit Status" }}
      submitLabel={{ create: "Create Status", edit: "Update Status" }}
      loadingLabel={{ create: "Creating...", edit: "Updating..." }}
      successMessage={{
        create: "Status created successfully.",
        edit: "Status updated successfully.",
      }}
      errorMessage={(err, m) =>
        extractErrorMessage(err, `Failed to ${m} status`)
      }
      errorDisplay="both"
      submitDisabled={(form) =>
        form.mode === "edit" &&
        !!statusToEdit &&
        Object.keys(changedFields(statusToEdit, form.values)).length === 0
      }
      validate={(values) => {
        const errors: FieldErrors<IssueStatusFormValues> = {};
        const keyError =
          mode === "create" ? issueStatusKeyError(values.key) : null;
        if (keyError) errors.key = keyError;
        if (!values.label.trim()) errors.label = "Label is required";
        return Object.keys(errors).length > 0 ? errors : null;
      }}
      onSubmit={async (values, { mode: m }) => {
        if (m === "create") {
          await createIssueStatus({
            key: values.key.trim(),
            label: values.label.trim(),
            category: values.category,
            color: values.color,
          });
        } else {
          if (!statusToEdit?.id) {
            throw new Error("Status ID is missing for update");
          }
          await updateIssueStatus(
            statusToEdit.id,
            changedFields(statusToEdit, values),
          );
        }
      }}
      onSuccess={() => onStatusSaved()}
    >
      {({ values, setField, errors, mode: m }) => (
        <>
          <FormField id="label" label="Label" error={errors.label}>
            <Input
              id="label"
              value={values.label}
              onChange={(e) => setField("label", e.target.value)}
              placeholder="Under review"
              maxLength={100}
              autoFocus
            />
          </FormField>

          <FormField id="key" label="Key" error={errors.key}>
            <Input
              id="key"
              value={values.key}
              onChange={(e) => setField("key", e.target.value)}
              placeholder="under_review"
              disabled={m === "edit"}
              maxLength={50}
            />
          </FormField>

          <FormField id="category" label="Category">
            <Select
              value={values.category}
              onValueChange={(value) =>
                setField("category", value as IssueCategory)
              }
              disabled={isDefault}
            >
              <SelectTrigger id="category">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(Object.keys(CATEGORY_META) as IssueCategory[]).map(
                  (category) => (
                    <SelectItem key={category} value={category}>
                      {CATEGORY_META[category].label}
                    </SelectItem>
                  ),
                )}
              </SelectContent>
            </Select>
            {isDefault && (
              <p className="mt-1 text-xs text-muted-foreground">
                The default status always stays in To Do
              </p>
            )}
          </FormField>

          <FormField id="color" label="Colour">
            <Select
              value={values.color}
              onValueChange={(value) => setField("color", value)}
            >
              <SelectTrigger id="color">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(STATUS_COLOR_CLASSES).map(
                  ([color, className]) => (
                    <SelectItem key={color} value={color}>
                      <span
                        className={cn(
                          badgeVariants({ variant: "outline" }),
                          className,
                          "capitalize",
                        )}
                      >
                        {color}
                      </span>
                    </SelectItem>
                  ),
                )}
              </SelectContent>
            </Select>
          </FormField>
        </>
      )}
    </CRUDDialog>
  );
}
