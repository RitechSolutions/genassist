import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/switch";
import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import { Checkbox } from "@/components/checkbox";
import { ScrollArea } from "@/components/scroll-area";
import { AlertCircle, Loader2, Plus, Trash2 } from "lucide-react";
import { toast } from "react-hot-toast";
import {
  createLLMAnalyst,
  updateLLMAnalyst,
  getAllLLMProviders,
  getAvailableEnrichments,
  getAvailableNodeTypes,
} from "@/services/llmAnalyst";
import { AvailableEnrichment, AvailableNodeType, LLMAnalyst, LLMProvider } from "@/interfaces/llmAnalyst.interface";
import { cn } from "@/helpers/utils";
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
import { TagsFieldInput } from "@/components/TagsFieldInput";
import {
  applySubtopicEdit,
  DEFAULT_ANALYST_TOPICS,
  parseTopicRows,
  serializeTopicRows,
  topicNameError,
  type TopicRow,
} from "../helpers/topicRows";

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

type KeyedTopicRow = TopicRow & { key: number };

const ANALYST_TABS = [
  { value: "general", label: "General" },
  { value: "topics", label: "Topics" },
  { value: "advanced", label: "Advanced" },
];

export function LLMAnalystDialog({
  isOpen,
  onOpenChange,
  onAnalystSaved,
  analystToEdit = null,
  mode = "create",
}: LLMAnalystDialogProps) {
  const queryClient = useQueryClient();
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [isLoadingProviders, setIsLoadingProviders] = useState(true);
  const [isCreateProviderOpen, setIsCreateProviderOpen] = useState(false);
  const [availableEnrichments, setAvailableEnrichments] = useState<AvailableEnrichment[]>([]);
  const [selectedEnrichments, setSelectedEnrichments] = useState<string[]>([]);
  const [availableNodeTypes, setAvailableNodeTypes] = useState<AvailableNodeType[]>([]);
  const [nodeTypeSearch, setNodeTypeSearch] = useState("");
  const [topicRows, setTopicRows] = useState<KeyedTopicRow[]>([]);
  const [selectedTopicKey, setSelectedTopicKey] = useState<number | null>(null);
  const [newTopicName, setNewTopicName] = useState("");
  const nextRowKey = useRef(0);

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

  const withRowKey = (row: TopicRow): KeyedTopicRow => ({ ...row, key: nextRowKey.current++ });

  const updateTopicRow = (index: number, patch: Partial<TopicRow>) =>
    setTopicRows((rows) => rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));

  const selectedTopic =
    topicRows.find((row) => row.key === selectedTopicKey) ?? topicRows[0] ?? null;
  const selectedIndex = selectedTopic ? topicRows.indexOf(selectedTopic) : -1;
  const selectedTopicError = selectedTopic
    ? topicNameError(selectedTopic.name, topicRows, selectedIndex)
    : null;

  const newTopicError = newTopicName.trim() ? topicNameError(newTopicName, topicRows) : null;
  const topicsInvalid =
    newTopicError !== null ||
    topicRows.some((row, i) => topicNameError(row.name, topicRows, i) !== null);

  const addTopicRow = () => {
    if (!newTopicName.trim() || newTopicError) return;
    const row = withRowKey({ name: newTopicName.trim(), subtopics: [] });
    setTopicRows((rows) => [...rows, row]);
    setSelectedTopicKey(row.key);
    setNewTopicName("");
  };

  const removeTopicRow = (key: number) => {
    const index = topicRows.findIndex((row) => row.key === key);
    const neighbour = topicRows[index + 1] ?? topicRows[index - 1];
    setTopicRows((rows) => rows.filter((row) => row.key !== key));
    setSelectedTopicKey(neighbour?.key ?? null);
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
    setTopicRows([]);
    setSelectedTopicKey(null);
    setNewTopicName("");
    fetchProviders();
    fetchEnrichments();
    fetchNodeTypes();
    if (analystToEdit && mode === "edit") {
      setSelectedEnrichments(analystToEdit.context_enrichments ?? []);
      setTopicRows(parseTopicRows(analystToEdit.settings?.topics).map(withRowKey));
    }
  }, [isOpen, analystToEdit, mode]);

  return (
    <CRUDDialog<LLMAnalystFormValues>
      open={isOpen}
      onOpenChange={onOpenChange}
      mode={mode}
      maxWidth="720px"
      bodyClassName="space-y-4"
      tabs={ANALYST_TABS}
      submitDisabled={topicsInvalid}
      footerStart={(form) =>
        topicsInvalid && form.activeTab !== "topics" ? (
          <Button
            type="button"
            variant="link"
            size="sm"
            className="px-0 text-destructive"
            onClick={() => form.setActiveTab("topics")}
          >
            <AlertCircle />
            Fix the topics to save
          </Button>
        ) : null
      }
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
        const { topics: _, ...otherSettings }: Record<string, unknown> =
          (m === "edit" && analystToEdit?.settings) || {};
        const pendingTopic = newTopicName.trim();
        const topics = serializeTopicRows(
          pendingTopic ? [...topicRows, { name: pendingTopic, subtopics: [] }] : topicRows,
        );
        const merged = topics.length > 0 ? { ...otherSettings, topics } : otherSettings;
        const base = {
          llm_provider_id: values.llm_provider_id,
          prompt: normalizedPrompt,
          is_active: values.is_active ? 1 : 0,
          context_enrichments: selectedEnrichments,
          settings: Object.keys(merged).length > 0 ? merged : null,
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
      onSuccess={() => {
        queryClient.invalidateQueries({ queryKey: ["topic-options"] });
        onAnalystSaved();
      }}
    >
      {(form) => (
        <>
          {/* General tab */}
          <div className={form.activeTab === "general" ? "space-y-4" : "hidden"}>
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
          <div className={form.activeTab === "advanced" ? "flex h-[31.5rem] flex-col gap-4" : "hidden"}>
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
            <div className="flex min-h-0 flex-1 flex-col gap-2">
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
              <ScrollArea className="min-h-0 flex-1 border rounded-lg p-2">
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
          </div>

          {/* Topics tab */}
          <div className={form.activeTab === "topics" ? "space-y-4" : "hidden"}>
            <p className="text-xs text-muted-foreground">
              Each finished conversation gets one topic and, if one fits, a sub-topic. Live
              conversations get a topic only.
            </p>

            <div className="grid h-[29.5rem] grid-cols-[12rem_minmax(0,1fr)] grid-rows-[minmax(0,1fr)] overflow-hidden rounded-lg border">
              <div className="flex min-h-0 flex-col border-r bg-muted/30">
                <div className="min-h-0 flex-1 overflow-y-auto">
                  <div className="space-y-0.5 p-2">
                    {topicRows.map((row, i) => {
                      const isSelected = row.key === selectedTopic?.key;
                      const hasError = topicNameError(row.name, topicRows, i) !== null;
                      return (
                        <button
                          key={row.key}
                          type="button"
                          aria-pressed={isSelected}
                          onClick={() => setSelectedTopicKey(row.key)}
                          className={cn(
                            "flex w-full items-center justify-between gap-2 rounded-md px-2.5 py-2 text-left text-sm",
                            isSelected
                              ? "bg-background font-medium text-primary shadow-sm"
                              : "hover:bg-muted/50",
                          )}
                        >
                          <span
                            className={cn("truncate", !row.name.trim() && "italic text-muted-foreground")}
                          >
                            {row.name.trim() || "Untitled topic"}
                          </span>
                          {hasError ? (
                            <AlertCircle className="h-3.5 w-3.5 shrink-0 text-destructive" />
                          ) : (
                            <Badge variant="secondary" className="shrink-0 px-1.5 py-0 text-[10px]">
                              {row.subtopics.length}
                            </Badge>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
                <div className="space-y-1 border-t p-2">
                  <div className="flex gap-1">
                    <Input
                      className="h-9 text-sm"
                      placeholder="New topic"
                      aria-label="New topic name"
                      value={newTopicName}
                      onChange={(e) => setNewTopicName(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          addTopicRow();
                        }
                      }}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-9 w-9 shrink-0"
                      aria-label="Add topic"
                      disabled={!newTopicName.trim() || newTopicError !== null}
                      onClick={addTopicRow}
                    >
                      <Plus className="h-4 w-4" />
                    </Button>
                  </div>
                  {newTopicError && <p className="text-xs text-red-500">{newTopicError}</p>}
                </div>
              </div>

              {selectedTopic ? (
                <div key={selectedTopic.key} className="flex min-h-0 flex-col gap-4 overflow-y-auto p-4">
                  <FormField id="topic-name" label="Topic name" error={selectedTopicError ?? undefined}>
                    <Input
                      id="topic-name"
                      value={selectedTopic.name}
                      onChange={(e) => updateTopicRow(selectedIndex, { name: e.target.value })}
                    />
                  </FormField>
                  <FormField id="topic-subtopics" label="Sub-topics">
                    <TagsFieldInput
                      id="topic-subtopics"
                      className="min-h-24 content-start rounded-lg"
                      value={selectedTopic.subtopics}
                      onChange={(next) =>
                        updateTopicRow(selectedIndex, {
                          subtopics: applySubtopicEdit(selectedTopic.subtopics, next),
                        })
                      }
                    />
                  </FormField>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="mt-auto self-end text-destructive hover:text-destructive"
                    onClick={() => removeTopicRow(selectedTopic.key)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Remove
                  </Button>
                </div>
              ) : (
                <p className="p-4 text-xs text-muted-foreground">
                  No topics yet, so the analyst uses the defaults: {DEFAULT_ANALYST_TOPICS.join(", ")}.
                </p>
              )}
            </div>
          </div>
        </>
      )}
    </CRUDDialog>
  );
}
