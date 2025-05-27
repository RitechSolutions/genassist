import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
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
      toast.error("Failed to load LLM providers");
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
    if (!name || !llmProviderId || !prompt) {
      toast.error("All fields are required");
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
        toast.success("LLM Analyst created successfully");
      } else {
        if (!analystId) {
          toast.error("Missing analyst ID");
          return;
        }
        const { name: _, ...rest } = data;
        await updateLLMAnalyst(analystId, rest);
        toast.success("LLM Analyst updated successfully");
      }

      onAnalystSaved();
      onOpenChange(false);
      resetForm();
    } catch (error) {
      toast.error(
        `Failed to ${mode === "create" ? "create" : "update"} LLM Analyst`
      );
      console.error(error);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]" aria-describedby="dialog-description">
        <DialogHeader>
          <DialogTitle>
            {mode === "create" ? "Create LLM Analyst" : "Edit LLM Analyst"}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="llm_provider">LLM Provider</Label>
            {isLoadingProviders ? (
              <Loader2 className="w-6 h-6 animate-spin" />
            ) : (
              <Select
                value={llmProviderId}
                onValueChange={(value) => setLlmProviderId(value)}
              >
                <SelectTrigger className="w-full border border-input rounded-xl px-3 py-2">
                  <SelectValue placeholder="Select a provider" />
                </SelectTrigger>
                <SelectContent>
                  {providers.map((provider) => (
                    <>
                    <SelectItem key={provider.id} value={provider.id}>
                      {`${provider.llm_type} - ${provider.model_name}`}
                    </SelectItem>
                    </>
                  ))}
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

          <DialogFooter>
            <Button type="submit" disabled={isSubmitting} className="w-full">
              {isSubmitting ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : null}
              {mode === "create" ? "Create" : "Update"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
