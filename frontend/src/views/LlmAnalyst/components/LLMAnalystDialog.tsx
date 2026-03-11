import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Textarea } from "@/components/textarea";
import { Switch } from "@/components/switch";
import { Button } from "@/components/button";
import { Checkbox } from "@/components/checkbox";
import { ScrollArea } from "@/components/scroll-area";
import { Loader2 } from "lucide-react";
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

interface LLMAnalystDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onAnalystSaved: () => void;
  analystToEdit?: LLMAnalyst | null;
  mode?: "create" | "edit";
}

export function LLMAnalystDialog({
  isOpen,
  onOpenChange,
  onAnalystSaved,
  analystToEdit = null,
  mode = "create",
}: LLMAnalystDialogProps) {
  const [name, setName] = useState("");
  const [llmProviderId, setLlmProviderId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [analystId, setAnalystId] = useState<string | undefined>();
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [isLoadingProviders, setIsLoadingProviders] = useState(true);
  const [isCreateProviderOpen, setIsCreateProviderOpen] = useState(false);
  const [availableEnrichments, setAvailableEnrichments] = useState<AvailableEnrichment[]>([]);
  const [selectedEnrichments, setSelectedEnrichments] = useState<string[]>([]);
  const [availableNodeTypes, setAvailableNodeTypes] = useState<AvailableNodeType[]>([]);
  const [nodeTypeSearch, setNodeTypeSearch] = useState("");

  useEffect(() => {
    if (isOpen) {
      resetForm();
      fetchProviders();
      fetchEnrichments();
      fetchNodeTypes();
      if (analystToEdit && mode === "edit") {
        populateFormWithAnalyst(analystToEdit);
      }
    }
  }, [isOpen, analystToEdit, mode]);

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

  const populateFormWithAnalyst = (analyst: LLMAnalyst) => {
    setAnalystId(analyst.id);
    setName(analyst.name);
    setLlmProviderId(analyst.llm_provider_id);
    setPrompt(analyst.prompt);
    setIsActive(analyst.is_active === 1);
    setSelectedEnrichments(analyst.context_enrichments ?? []);
  };

  const resetForm = () => {
    setAnalystId(undefined);
    setName("");
    setLlmProviderId("");
    setPrompt("");
    setIsActive(true);
    setSelectedEnrichments([]);
    setNodeTypeSearch("");
  };

  const toggleEnrichment = (key: string) => {
    setSelectedEnrichments((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const requiredFields = [
      { label: "LLM Provider", isEmpty: !llmProviderId },
      { label: "Name", isEmpty: !name },
      { label: "Prompt", isEmpty: !prompt },
    ];

    const missingFields = requiredFields
      .filter((field) => field.isEmpty)
      .map((field) => field.label);

    if (missingFields.length > 0) {
      if (missingFields.length === 1) {
        toast.error(`${missingFields[0]} is required.`);
      } else {
        toast.error(`Please provide: ${missingFields.join(", ")}.`);
      }
      return;
    }

    setIsSubmitting(true);
    try {
      const data = {
        name,
        llm_provider_id: llmProviderId,
        prompt,
        is_active: isActive ? 1 : 0,
        context_enrichments: selectedEnrichments,
      };

      if (mode === "create") {
        await createLLMAnalyst(data);
        toast.success("LLM analyst created successfully.");
      } else {
        if (!analystId) {
          toast.error("Analyst ID is required.");
          return;
        }
        const { name: _, ...rest } = data;
        await updateLLMAnalyst(analystId, rest);
        toast.success("LLM analyst updated successfully.");
      }

      onAnalystSaved();
      onOpenChange(false);
      resetForm();
    } catch (error) {
      toast.error(
        `Failed to ${mode === "create" ? "create" : "update"} LLM analyst${
          error.status === 400
            ? ": An LLM analyst with this name already exists"
            : ""
        }.`
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <Dialog open={isOpen} onOpenChange={onOpenChange}>
        <DialogContent
          className="sm:max-w-[600px] p-0 overflow-hidden"
          aria-describedby="dialog-description"
        >
          <form
            onSubmit={handleSubmit}
            className="max-h-[90vh] overflow-y-auto overflow-x-hidden flex flex-col"
          >
            <DialogHeader className="p-6 pb-4">
              <DialogTitle>
                {mode === "create" ? "Create LLM Analyst" : "Edit LLM Analyst"}
              </DialogTitle>
            </DialogHeader>
            <div className="px-6 pb-6 space-y-4">
              <div className="space-y-2">
                <Label htmlFor="llm_provider">LLM Provider</Label>
                {isLoadingProviders ? (
                  <Loader2 className="w-6 h-6 animate-spin" />
                ) : (
                  <Select
                    value={llmProviderId || ""}
                    onValueChange={(value) => {
                      if (value === "__create__") {
                        setIsCreateProviderOpen(true);
                        return;
                      }
                      setLlmProviderId(value);
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
              </div>

              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Analyst name"
                  disabled={mode === "edit"}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="prompt">Prompt</Label>
                <Textarea
                  id="prompt"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value.replace(/\s+/g, ' '))}
                  placeholder="System prompt"
                  rows={6}
                />
              </div>

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

              <div className="flex items-center gap-2">
                <Label htmlFor="is_active">Active</Label>
                <Switch
                  id="is_active"
                  checked={isActive}
                  onCheckedChange={setIsActive}
                />
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
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : null}
                  {mode === "create" ? "Create" : "Update"}
                </Button>
              </div>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
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
            setLlmProviderId(provider.id);
          }
        }}
        mode="create"
      />
    </>
  );
}