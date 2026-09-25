import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/switch";
import { Button } from "@/components/button";
import { Checkbox } from "@/components/checkbox";
import { ScrollArea } from "@/components/scroll-area";
import { Badge } from "@/components/badge";
import { Loader2, X, Plus, Trash2 } from "lucide-react";
import { toast } from "react-hot-toast";
import {
  createLLMAnalyst,
  updateLLMAnalyst,
  getAllLLMProviders,
  getAvailableEnrichments,
  getAvailableNodeTypes,
} from "@/services/llmAnalyst";
import { AvailableEnrichment, AvailableNodeType, LLMAnalyst, LLMProvider } from "@/interfaces/llmAnalyst.interface";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/select";
import { LLMProviderDialog } from "@/views/LlmProviders/components/LLMProviderDialog";
import { CreateNewSelectItem } from "@/components/CreateNewSelectItem";
import { FormField } from "@/components/ui/form-field";
import { CRUDDialog, type FieldErrors } from "@/components/ui/crud-dialog";

interface LLMAnalystDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onAnalystSaved: () => void;
  analystToEdit?: LLMAnalyst | null;
  mode?: "create" | "edit";
}

type LLMAnalystFormValues = {
  name: string;
  llm_provider_id: string;
  prompt: string;
  is_active: boolean;
};

const ANALYST_TABS = [
  { value: "general", label: "General" },
  { value: "advanced", label: "Advanced" },
];

export function LLMAnalystDialog({
  isOpen,
  onOpenChange,
  onAnalystSaved,
  analystToEdit = null,
  mode = "create",
}: LLMAnalystDialogProps) {
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [isLoadingProviders, setIsLoadingProviders] = useState(true);
  const [isCreateProviderOpen, setIsCreateProviderOpen] = useState(false);
  const [availableEnrichments, setAvailableEnrichments] = useState<AvailableEnrichment[]>([]);
  const [selectedEnrichments, setSelectedEnrichments] = useState<string[]>([]);
  const [availableNodeTypes, setAvailableNodeTypes] = useState<AvailableNodeType[]>([]);
  const [nodeTypeSearch, setNodeTypeSearch] = useState("");
  const [settings, setSettings] = useState<Record<string, unknown>>({});
  const [newFieldKey, setNewFieldKey] = useState("");
  const [tagInputs, setTagInputs] = useState<Record<string, string>>({});

  const fetchProviders = async () => {
    setIsLoadingProviders(true);
    try {
      const result = await getAllLLMProviders();
      setProviders(result.filter((p) => p.is_active === 1));
    } catch {
      toast.error("Failed to fetch LLM providers.");
    } finally {
      setIsLoadingProviders(false);
    }
  };

  const fetchEnrichments = async () => {
    try {
      const result = await getAvailableEnrichments();
      setAvailableEnrichments(result);
    } catch {
      // non-critical, silently ignore
    }
  };

  const fetchNodeTypes = async () => {
    try {
      const result = await getAvailableNodeTypes();
      setAvailableNodeTypes(result);
    } catch {
      // non-critical, silently ignore
    }
  };

  const toggleEnrichment = (key: string) => {
    setSelectedEnrichments((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  };

  // Extra (non form-value) state is reset/populated here; the scalar form
  // values (name, llm_provider_id, prompt, is_active) are owned by CRUDDialog
  // via initialValues/editValues keyed on resetKey.
  useEffect(() => {
    if (!isOpen) return;
    setSelectedEnrichments([]);
    setNodeTypeSearch("");
    setSettings({});
    setTagInputs({});
    setNewFieldKey("");
    fetchProviders();
    fetchEnrichments();
    fetchNodeTypes();
    if (analystToEdit && mode === "edit") {
      setSelectedEnrichments(analystToEdit.context_enrichments ?? []);
      setSettings(analystToEdit.settings ?? {});
    }
  }, [isOpen, analystToEdit, mode]);

  return (
    <CRUDDialog<LLMAnalystFormValues>
      open={isOpen}
      onOpenChange={onOpenChange}
      mode={mode}
      maxWidth="600px"
      bodyClassName="space-y-4"
      tabs={ANALYST_TABS}
      resetKey={analystToEdit?.id ?? null}
      initialValues={{ name: "", llm_provider_id: "", prompt: "", is_active: true }}
      editValues={
        analystToEdit
          ? {
              name: analystToEdit.name,
              llm_provider_id: analystToEdit.llm_provider_id,
              prompt: analystToEdit.prompt,
              is_active: analystToEdit.is_active === 1,
            }
          : null
      }
      title={{ create: "Create LLM Analyst", edit: "Edit LLM Analyst" }}
      submitLabel={{ create: "Create", edit: "Update" }}
      loadingLabel={{ create: "Create", edit: "Update" }}
      successMessage={{
        create: "LLM analyst created successfully.",
        edit: "LLM analyst updated successfully.",
      }}
      errorMessage={(err, m) => {
        if ((err as { isGuard?: boolean } | null)?.isGuard) {
          return "Analyst ID is required.";
        }
        const status = (err as { status?: number } | null)?.status;
        return `Failed to ${m === "create" ? "create" : "update"} LLM analyst${
          status === 400
            ? ": An LLM analyst with this name already exists"
            : ""
        }.`;
      }}
      validate={(values) => {
        const errors: FieldErrors<LLMAnalystFormValues> = {};
        if (!values.llm_provider_id)
          errors.llm_provider_id = "LLM Provider is required.";
        if (!values.name) errors.name = "Name is required.";
        if (!values.prompt.trim()) errors.prompt = "Prompt is required.";
        return Object.keys(errors).length > 0 ? errors : null;
      }}
      onSubmit={async (values, { mode: m }) => {
        const normalizedPrompt = values.prompt.trim().replace(/\s+/g, " ");
        const base = {
          llm_provider_id: values.llm_provider_id,
          prompt: normalizedPrompt,
          is_active: values.is_active ? 1 : 0,
          context_enrichments: selectedEnrichments,
          settings: Object.keys(settings).length > 0 ? settings : null,
        };

        if (m === "create") {
          await createLLMAnalyst({ name: values.name, ...base });
        } else {
          if (!analystToEdit?.id) {
            const guard = new Error("Analyst ID is required.");
            (guard as { isGuard?: boolean }).isGuard = true;
            throw guard;
          }
          await updateLLMAnalyst(analystToEdit.id, base);
        }
      }}
      onSuccess={() => onAnalystSaved()}
    >
      {(form) => (
        <>
          {/* General tab */}
          <div className={form.activeTab === "advanced" ? "hidden" : "space-y-4"}>
          <div className="space-y-2">
            <Label htmlFor="llm_provider">LLM Provider</Label>
            {isLoadingProviders ? (
              <Loader2 className="w-6 h-6 animate-spin" />
            ) : (
              <Select
                value={form.values.llm_provider_id || ""}
                onValueChange={(value) => {
                  if (value === "__create__") {
                    setIsCreateProviderOpen(true);
                    return;
                  }
                  form.setField("llm_provider_id", value);
                }}
              >
                <SelectTrigger className="w-full border border-input rounded-xl px-3 py-2">
                  <SelectValue placeholder="Select a provider" />
                </SelectTrigger>
                <SelectContent>
                  {providers.map((provider) => (
                    <SelectItem key={provider.id} value={provider.id}>
                      {`${provider.name} -  (${provider.llm_model})`}
                    </SelectItem>
                  ))}
                  <CreateNewSelectItem />
                </SelectContent>
              </Select>
            )}
            {form.errors.llm_provider_id && (
              <p className="text-sm text-red-500 mt-1">
                {form.errors.llm_provider_id}
              </p>
            )}
          </div>

          <FormField id="name" label="Name" error={form.errors.name}>
            <Input
              id="name"
              value={form.values.name}
              onChange={(e) => form.setField("name", e.target.value)}
              placeholder="Analyst name"
              disabled={form.mode === "edit"}
            />
          </FormField>

          <FormField id="prompt" label="Prompt" error={form.errors.prompt}>
            <Textarea
              id="prompt"
              value={form.values.prompt}
              onChange={(e) => form.setField("prompt", e.target.value)}
              placeholder="System prompt"
              size="prompt"
              className="font-mono text-sm"
            />
          </FormField>

          <div className="flex items-center gap-2 border-t pt-4">
            <Label htmlFor="is_active">Active</Label>
            <Switch
              id="is_active"
              checked={form.values.is_active}
              onCheckedChange={(checked) => form.setField("is_active", checked)}
            />
          </div>

          <LLMProviderDialog
            isOpen={isCreateProviderOpen}
            onOpenChange={setIsCreateProviderOpen}
            onProviderSaved={async (provider) => {
              try {
                await fetchProviders();
              } catch {
                // ignore
              }
              if (provider?.id) {
                form.setField("llm_provider_id", provider.id);
              }
            }}
            mode="create"
          />
          </div>

          {/* Advanced tab */}
          <div className={form.activeTab === "advanced" ? "space-y-4" : "hidden"}>
          {availableEnrichments.length > 0 && (
            <div className="space-y-2">
              <Label>Context Enrichments</Label>
              <p className="text-xs text-muted-foreground">
                Select additional conversation data to include when analyzing transcripts.
              </p>
              <div className="border rounded-lg p-2 space-y-1 overflow-y-auto max-h-40">
                {availableEnrichments.map((enrichment) => (
                  <div
                    key={enrichment.key}
                    className="flex items-start gap-3 p-2 rounded-md hover:bg-muted/50"
                  >
                    <Checkbox
                      id={`enrichment-${enrichment.key}`}
                      checked={selectedEnrichments.includes(enrichment.key)}
                      onCheckedChange={() => toggleEnrichment(enrichment.key)}
                      className="mt-0.5"
                    />
                    <div className="flex-1 min-w-0">
                      <label
                        htmlFor={`enrichment-${enrichment.key}`}
                        className="text-sm font-medium cursor-pointer"
                      >
                        {enrichment.name}
                      </label>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {enrichment.description}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {availableNodeTypes.length > 0 && (
            <div className="space-y-2">
              <Label>Node Enrichments</Label>
              <p className="text-xs text-muted-foreground">
                Appends "{`<Node> node used: Yes/No`}" to the prompt for each selected node. Reference this in your prompt instructions.
              </p>
              <Input
                placeholder="Search nodes..."
                value={nodeTypeSearch}
                onChange={(e) => setNodeTypeSearch(e.target.value)}
                className="h-8 text-sm"
              />
              <ScrollArea className="border rounded-lg p-2 h-48">
                <div className="space-y-1">
                  {availableNodeTypes
                    .filter((n) =>
                      n.label.toLowerCase().includes(nodeTypeSearch.toLowerCase())
                    )
                    .map((n) => (
                      <div
                        key={n.node_type}
                        className="flex items-center gap-3 p-2 rounded-md hover:bg-muted/50"
                      >
                        <Checkbox
                          id={`node-${n.node_type}`}
                          checked={selectedEnrichments.includes(`node:${n.node_type}`)}
                          onCheckedChange={() => toggleEnrichment(`node:${n.node_type}`)}
                        />
                        <label
                          htmlFor={`node-${n.node_type}`}
                          className="text-sm cursor-pointer"
                        >
                          {n.label}
                        </label>
                      </div>
                    ))}
                </div>
              </ScrollArea>
            </div>
          )}

          <div className="space-y-2">
            <Label>Analyst Settings</Label>
            <p className="text-xs text-muted-foreground">
              Key-value settings passed to the analyst (e.g. topics list for conversation analysis).
            </p>
            <div className="border rounded-lg p-3 space-y-3">
              {Object.entries(settings).map(([key, value]) => (
                <div key={key} className="space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">{key}</span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 text-muted-foreground hover:text-destructive"
                      onClick={() => {
                        const next = { ...settings };
                        delete next[key];
                        setSettings(next);
                      }}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                  {Array.isArray(value) ? (
                    <div className="space-y-1.5">
                      <div className="flex flex-wrap gap-1.5">
                        {value.map((tag: string) => (
                          <Badge key={tag} variant="secondary" className="gap-1 pr-1">
                            {tag}
                            <button
                              type="button"
                              className="ml-0.5 hover:text-destructive"
                              onClick={() =>
                                setSettings((prev) => ({
                                  ...prev,
                                  [key]: (prev[key] as string[]).filter((t) => t !== tag),
                                }))
                              }
                            >
                              <X className="h-3 w-3" />
                            </button>
                          </Badge>
                        ))}
                      </div>
                      <div className="flex gap-2">
                        <Input
                          className="h-7 text-sm"
                          placeholder="Add item..."
                          value={tagInputs[key] ?? ""}
                          onChange={(e) =>
                            setTagInputs((prev) => ({ ...prev, [key]: e.target.value }))
                          }
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              e.preventDefault();
                              const val = (tagInputs[key] ?? "").trim();
                              if (val && !(value as string[]).includes(val)) {
                                setSettings((prev) => ({
                                  ...prev,
                                  [key]: [...(prev[key] as string[]), val],
                                }));
                                setTagInputs((prev) => ({ ...prev, [key]: "" }));
                              }
                            }
                          }}
                        />
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          className="h-7 px-2"
                          disabled={!(tagInputs[key] ?? "").trim()}
                          onClick={() => {
                            const val = (tagInputs[key] ?? "").trim();
                            if (val && !(value as string[]).includes(val)) {
                              setSettings((prev) => ({
                                ...prev,
                                [key]: [...(prev[key] as string[]), val],
                              }));
                              setTagInputs((prev) => ({ ...prev, [key]: "" }));
                            }
                          }}
                        >
                          <Plus className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <Input
                      className="h-7 text-sm"
                      value={String(value)}
                      onChange={(e) =>
                        setSettings((prev) => ({ ...prev, [key]: e.target.value }))
                      }
                    />
                  )}
                </div>
              ))}
              <div className={`flex gap-2 pt-1 ${Object.keys(settings).length > 0 ? 'border-t' : ''}`}>
                <Input
                  className="h-7 text-sm"
                  placeholder="New field name..."
                  value={newFieldKey}
                  onChange={(e) => setNewFieldKey(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      const k = newFieldKey.trim();
                      if (k && !(k in settings)) {
                        setSettings((prev) => ({ ...prev, [k]: [] }));
                        setNewFieldKey("");
                      }
                    }
                  }}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 px-2 shrink-0"
                  disabled={!newFieldKey.trim()}
                  onClick={() => {
                    const k = newFieldKey.trim();
                    if (k && !(k in settings)) {
                      setSettings((prev) => ({ ...prev, [k]: [] }));
                      setNewFieldKey("");
                    }
                  }}
                >
                  <Plus className="h-3.5 w-3.5" />
                  Add Field
                </Button>
              </div>
            </div>
          </div>
          </div>
        </>
      )}
    </CRUDDialog>
  );
}
