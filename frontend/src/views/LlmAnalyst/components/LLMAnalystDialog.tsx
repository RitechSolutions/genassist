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
import { Loader2 } from "lucide-react";
import { toast } from "react-hot-toast";
import {
  createLLMAnalyst,
  updateLLMAnalyst,
  getAllLLMProviders,
} from "@/services/llmAnalyst";
import { LLMAnalyst, LLMProvider } from "@/interfaces/llmAnalyst.interface";
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

  useEffect(() => {
    if (isOpen) {
      resetForm();
      fetchProviders();
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

  const populateFormWithAnalyst = (analyst: LLMAnalyst) => {
    setAnalystId(analyst.id);
    setName(analyst.name);
    setLlmProviderId(analyst.llm_provider_id);
    setPrompt(analyst.prompt);
    setIsActive(analyst.is_active === 1);
  };

  const resetForm = () => {
    setAnalystId(undefined);
    setName("");
    setLlmProviderId("");
    setPrompt("");
    setIsActive(true);
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
                  value={prompt.trim().replace(/\s+/g, " ")}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="System prompt"
                  rows={6}
                />
              </div>

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
