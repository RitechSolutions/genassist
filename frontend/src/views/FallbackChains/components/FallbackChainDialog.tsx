import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/label";
import { Switch } from "@/components/switch";
import { Button } from "@/components/button";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/select";
import { Badge } from "@/components/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/RadixTooltip";
import { Loader2, ArrowUp, ArrowDown, X, Info } from "lucide-react";
import { toast } from "react-hot-toast";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createFallbackChain,
  updateFallbackChain,
} from "@/services/fallbackChains";
import { getAllLLMProviders } from "@/services/llmProviders";
import { FallbackChain } from "@/interfaces/fallbackChain.interface";

interface FallbackChainDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onChainSaved: () => void;
  chainToEdit?: FallbackChain | null;
  mode?: "create" | "edit";
}

export function FallbackChainDialog({
  isOpen,
  onOpenChange,
  onChainSaved,
  chainToEdit = null,
  mode = "create",
}: FallbackChainDialogProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [providerIds, setProviderIds] = useState<string[]>([]);
  const [retryCount, setRetryCount] = useState(2);
  const [backoffSeconds, setBackoffSeconds] = useState(1);
  const [timeoutSeconds, setTimeoutSeconds] = useState<number | "">("");
  const [providerTimeouts, setProviderTimeouts] = useState<Record<string, number>>({});
  const [isActive, setIsActive] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const queryClient = useQueryClient();

  const { data: providers = [] } = useQuery({
    queryKey: ["llmProviders"],
    queryFn: getAllLLMProviders,
    enabled: isOpen,
  });

  useEffect(() => {
    if (!isOpen) return;
    setName(chainToEdit?.name ?? "");
    setDescription(chainToEdit?.description ?? "");
    setProviderIds(chainToEdit?.provider_ids ?? []);
    setRetryCount(chainToEdit?.retry_policy?.retry_count ?? 2);
    setBackoffSeconds(chainToEdit?.retry_policy?.backoff_seconds ?? 1);
    setTimeoutSeconds(
      Number(chainToEdit?.retry_policy?.timeout_seconds) > 0
        ? (chainToEdit!.retry_policy!.timeout_seconds as number)
        : ""
    );
    setProviderTimeouts(
      Object.fromEntries(
        Object.entries(chainToEdit?.retry_policy?.provider_timeouts ?? {}).filter(
          ([, v]) => Number(v) > 0
        )
      )
    );
    setIsActive(chainToEdit ? chainToEdit.is_active === 1 : true);
  }, [isOpen, chainToEdit]);

  const providerName = (id: string) =>
    providers.find((p) => p.id === id)?.name ?? id;

  const availableProviders = providers.filter(
    (p) => p.is_active === 1 && !providerIds.includes(p.id)
  );

  const addProvider = (id: string) => {
    if (id && !providerIds.includes(id)) setProviderIds((prev) => [...prev, id]);
  };

  const removeProvider = (id: string) => {
    setProviderIds((prev) => prev.filter((p) => p !== id));
    setProviderTimeouts((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  };

  // Blank/0/invalid clears the override (the provider then inherits the chain
  // default), so the field shows empty rather than a confusing 0.
  const setProviderTimeout = (id: string, raw: string) =>
    setProviderTimeouts((prev) => {
      const next = { ...prev };
      const n = Number(raw);
      if (raw === "" || Number.isNaN(n) || n <= 0) {
        delete next[id];
      } else {
        next[id] = n;
      }
      return next;
    });

  const move = (index: number, delta: number) => {
    setProviderIds((prev) => {
      const next = [...prev];
      const target = index + delta;
      if (target < 0 || target >= next.length) return prev;
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };

  const handleSubmit = async () => {
    if (!name.trim()) {
      toast.error("Please enter a chain name.");
      return;
    }
    if (providerIds.length < 1) {
      toast.error("Add at least one provider to the chain.");
      return;
    }
    setIsSubmitting(true);
    try {
      const payload = {
        name: name.trim(),
        description: description.trim() || null,
        provider_ids: providerIds,
        retry_policy: {
          retry_count: Number(retryCount) || 0,
          backoff_seconds: Number(backoffSeconds) || 0,
          timeout_seconds: Number(timeoutSeconds) || 0,
          provider_timeouts: Object.fromEntries(
            providerIds
              .filter((id) => Number(providerTimeouts[id]) > 0)
              .map((id) => [id, Number(providerTimeouts[id])])
          ),
        },
        is_active: isActive ? 1 : 0,
      };
      if (mode === "edit" && chainToEdit) {
        await updateFallbackChain(chainToEdit.id, payload);
        toast.success("Fallback chain updated.");
      } else {
        await createFallbackChain(payload as Omit<FallbackChain, "id" | "created_at" | "updated_at">);
        toast.success("Fallback chain created.");
      }
      queryClient.invalidateQueries({ queryKey: ["fallbackChains"] });
      onChainSaved();
      onOpenChange(false);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to save fallback chain."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {mode === "edit" ? "Edit Fallback Chain" : "Add Fallback Chain"}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="chain-name">Name</Label>
            <Input
              id="chain-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Production failover"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="chain-description">Description</Label>
            <Input
              id="chain-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional"
            />
          </div>

          <div className="space-y-2">
            <Label>Providers (priority order)</Label>
            <p className="text-xs text-muted-foreground">
              Tried top to bottom. The first provider is the primary; the rest are
              fallbacks used when the previous one fails.
            </p>
            {providerIds.length > 0 && (
              <div className="space-y-1">
                {providerIds.map((id, index) => (
                  <div
                    key={id}
                    className="flex items-center gap-2 rounded-md border p-2"
                  >
                    <Badge variant="outline">{index + 1}</Badge>
                    <span className="flex-1 truncate text-sm">
                      {providerName(id)}
                    </span>
                    <Input
                      type="number"
                      min={0}
                      max={600}
                      step={1}
                      className="w-32"
                      placeholder="timeout s"
                      title="Response timeout for this provider (seconds). Empty/0 uses the default."
                      value={providerTimeouts[id] ?? ""}
                      onChange={(e) => setProviderTimeout(id, e.target.value)}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      disabled={index === 0}
                      onClick={() => move(index, -1)}
                      title="Move up"
                    >
                      <ArrowUp className="h-4 w-4" />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      disabled={index === providerIds.length - 1}
                      onClick={() => move(index, 1)}
                      title="Move down"
                    >
                      <ArrowDown className="h-4 w-4" />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => removeProvider(id)}
                      title="Remove"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
            <Select value="" onValueChange={addProvider}>
              <SelectTrigger>
                <SelectValue placeholder="Add a provider…" />
              </SelectTrigger>
              <SelectContent>
                {availableProviders.length === 0 ? (
                  <SelectItem value="__none__" disabled>
                    No more active providers
                  </SelectItem>
                ) : (
                  availableProviders.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name} ({p.llm_model_provider} - {p.llm_model})
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
          </div>

          <TooltipProvider>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <div className="flex items-center gap-1.5">
                  <Label htmlFor="retry-count" className="whitespace-nowrap">Retries</Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className="inline-flex rounded-full text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                        aria-label="Retries per provider info"
                      >
                        <Info className="h-4 w-4" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-balance">
                      Extra attempts for the same provider (on retryable errors like
                      timeouts, rate limits, or 5xx) before moving to the next provider
                      in the chain. Total attempts = retries + 1. 0 = try once, then fail
                      over.
                    </TooltipContent>
                  </Tooltip>
                </div>
                <Input
                  id="retry-count"
                  type="number"
                  min={0}
                  max={10}
                  value={retryCount}
                  onChange={(e) => setRetryCount(Number(e.target.value))}
                />
              </div>
              <div className="space-y-2">
                <div className="flex items-center gap-1.5">
                  <Label htmlFor="backoff-seconds" className="whitespace-nowrap">Backoff (s)</Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className="inline-flex rounded-full text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                        aria-label="Initial backoff info"
                      >
                        <Info className="h-4 w-4" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-balance">
                      Seconds to wait before retrying the same provider. It doubles each
                      retry (exponential backoff): e.g. 1s → 2s → 4s. 0 = retry
                      immediately with no wait.
                    </TooltipContent>
                  </Tooltip>
                </div>
                <Input
                  id="backoff-seconds"
                  type="number"
                  min={0}
                  max={30}
                  step={0.5}
                  value={backoffSeconds}
                  onChange={(e) => setBackoffSeconds(Number(e.target.value))}
                />
              </div>
              <div className="space-y-2">
                <div className="flex items-center gap-1.5">
                  <Label htmlFor="timeout-seconds" className="whitespace-nowrap">Timeout (s)</Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className="inline-flex rounded-full text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                        aria-label="Default timeout info"
                      >
                        <Info className="h-4 w-4" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-balance">
                      If a provider takes longer than this to reply, the attempt is
                      cancelled and treated as a failure so the next provider is tried.
                      Applies to providers without their own per-provider timeout set in
                      the list above. Empty = no limit.
                    </TooltipContent>
                  </Tooltip>
                </div>
                <Input
                  id="timeout-seconds"
                  type="number"
                  min={0}
                  max={600}
                  step={1}
                  placeholder="no limit"
                  value={timeoutSeconds}
                  onChange={(e) =>
                    setTimeoutSeconds(e.target.value === "" ? "" : Number(e.target.value))
                  }
                />
              </div>
            </div>
          </TooltipProvider>

          <div className="flex items-center gap-2">
            <Switch checked={isActive} onCheckedChange={setIsActive} id="chain-active" />
            <Label htmlFor="chain-active">Active</Label>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {mode === "edit" ? "Save Changes" : "Create Chain"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
