import { Language } from "@/interfaces/translation.interface";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/label";
import { Switch } from "@/components/switch";
import { FormField } from "@/components/ui/form-field";
import { CRUDDialog } from "@/components/ui/crud-dialog";
import { extractErrorMessage } from "@/helpers/apiError";
import { createLanguage, updateLanguage } from "@/services/translations";

interface LanguageDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onLanguageSaved: () => void;
  languageToEdit?: Language | null;
  mode?: "create" | "edit";
}

type LanguageFormValues = {
  code: string;
  name: string;
  is_active: boolean;
};

export function LanguageDialog({
  isOpen,
  onOpenChange,
  onLanguageSaved,
  languageToEdit = null,
  mode = "create",
}: LanguageDialogProps) {
  return (
    <CRUDDialog<LanguageFormValues>
      open={isOpen}
      onOpenChange={onOpenChange}
      mode={mode}
      maxWidth="450px"
      resetKey={languageToEdit?.id ?? null}
      initialValues={{ code: "", name: "", is_active: true }}
      editValues={
        languageToEdit
          ? {
              code: languageToEdit.code ?? "",
              name: languageToEdit.name ?? "",
              is_active: languageToEdit.is_active,
            }
          : null
      }
      title={{ create: "Add New Language", edit: "Edit Language" }}
      submitLabel={{ create: "Create Language", edit: "Update Language" }}
      loadingLabel={{ create: "Creating...", edit: "Updating..." }}
      successMessage={{
        create: "Language created successfully.",
        edit: "Language updated successfully.",
      }}
      errorMessage={(err, m) => extractErrorMessage(err, `Failed to ${m} language`)}
      errorDisplay="both"
      validate={(values) => {
        if (!values.code.trim()) return { code: "Language code is required" };
        if (!values.name.trim()) return { name: "Language name is required" };
        return null;
      }}
      onSubmit={async (values, { mode: m }) => {
        if (m === "create") {
          await createLanguage({
            code: values.code.trim().toLowerCase(),
            name: values.name.trim(),
          });
        } else {
          if (!languageToEdit?.id) {
            throw new Error("Language ID is missing for update");
          }
          await updateLanguage(languageToEdit.id, {
            name: values.name.trim(),
            is_active: values.is_active,
          });
        }
      }}
      onSuccess={() => onLanguageSaved()}
    >
      {({ values, setField, errors, mode: m }) => (
        <>
          <FormField id="code" label="Code" error={errors.code}>
            <Input
              id="code"
              value={values.code}
              onChange={(e) => setField("code", e.target.value)}
              placeholder="en, fr, de, it..."
              disabled={m === "edit"}
              autoFocus={m === "create"}
              maxLength={10}
            />
            {m === "edit" && (
              <p className="mt-1 text-xs text-muted-foreground">
                Language code cannot be changed after creation
              </p>
            )}
          </FormField>

          <FormField id="name" label="Name" error={errors.name}>
            <Input
              id="name"
              value={values.name}
              onChange={(e) => setField("name", e.target.value)}
              placeholder="English, French, German..."
              autoFocus={m === "edit"}
            />
          </FormField>

          {m === "edit" && (
            <div className="flex items-center justify-between">
              <Label htmlFor="is_active" className="cursor-pointer">
                Active
              </Label>
              <Switch
                id="is_active"
                checked={values.is_active}
                onCheckedChange={(checked) => setField("is_active", checked)}
              />
            </div>
          )}
        </>
      )}
    </CRUDDialog>
  );
}
