import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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
import { ArrowUp, ArrowDown, X, Info } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FormField } from "@/components/ui/form-field";
import { CRUDDialog } from "@/components/ui/crud-dialog";
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

type FallbackChainFormValues = {
  name: string;
  description: string;
  provider_ids: string[];
  retry_count: number;
  backoff_seconds: number;
  timeout_seconds: number | "";
  provider_timeouts: Record<string, number>;
  is_active: boolean;
};

export function FallbackChainDialog({
  isOpen,
  onOpenChange,
  onChainSaved,
  chainToEdit = null,
  mode = "create",
}: FallbackChainDialogProps) {
  const queryClient = useQueryClient();

  const { data: providers = [] } = useQuery({
    queryKey: ["llmProviders"],
    queryFn: getAllLLMProviders,
    enabled: isOpen,
  });

  const providerName = (id: string) =>
    providers.find((p) => p.id === id)?.name ?? id;

  return (
    <CRUDDialog<FallbackChainFormValues>
      open={isOpen}
      onOpenChange={onOpenChange}
      mode={mode}
      maxWidth="512px"
      resetKey={chainToEdit?.id ?? null}
      initialValues={{
        name: "",
        description: "",
        provider_ids: [],
        retry_count: 2,
        backoff_seconds: 1,
        timeout_seconds: "",
        provider_timeouts: {},
        is_active: true,
      }}
      editValues={
        chainToEdit
          ? {
              name: chainToEdit.name ?? "",
              description: chainToEdit.description ?? "",
              provider_ids: chainToEdit.provider_ids ?? [],
              retry_count: chainToEdit.retry_policy?.retry_count ?? 2,
              backoff_seconds: chainToEdit.retry_policy?.backoff_seconds ?? 1,
              timeout_seconds:
                Number(chainToEdit.retry_policy?.timeout_seconds) > 0
                  ? (chainToEdit.retry_policy!.timeout_seconds as number)
                  : "",
              provider_timeouts: Object.fromEntries(
                Object.entries(
                  chainToEdit.retry_policy?.provider_timeouts ?? {}
                ).filter(([, v]) => Number(v) > 0)
              ),
              is_active: chainToEdit.is_active === 1,
            }
          : null
      }
      title={{ create: "Add Fallback Chain", edit: "Edit Fallback Chain" }}
      submitLabel={{ create: "Create Chain", edit: "Save Changes" }}
      loadingLabel={{ create: "Create Chain", edit: "Save Changes" }}
      successMessage={{
        create: "Fallback chain created.",
        edit: "Fallback chain updated.",
      }}
      errorMessage={(err) =>
        err instanceof Error ? err.message : "Failed to save fallback chain."
      }
      validate={(values) => {
        if (!values.name.trim()) return { name: "Please enter a chain name." };
        if (values.provider_ids.length < 1)
          return { provider_ids: "Add at least one provider to the chain." };
        return null;
      }}
      onSubmit={async (values, { mode: m }) => {
        const payload = {
          name: values.name.trim(),
          description: values.description.trim() || null,
          provider_ids: values.provider_ids,
          retry_policy: {
            retry_count: Number(values.retry_count) || 0,
            backoff_seconds: Number(values.backoff_seconds) || 0,
            timeout_seconds: Number(values.timeout_seconds) || 0,
            provider_timeouts: Object.fromEntries(
              values.provider_ids
                .filter((id) => Number(values.provider_timeouts[id]) > 0)
                .map((id) => [id, Number(values.provider_timeouts[id])])
            ),
          },
          is_active: values.is_active ? 1 : 0,
        };
        if (m === "edit" && chainToEdit) {
          await updateFallbackChain(chainToEdit.id, payload);
        } else {
          await createFallbackChain(
            payload as Omit<FallbackChain, "id" | "created_at" | "updated_at">
          );
        }
      }}
      onSuccess={() => {
        queryClient.invalidateQueries({ queryKey: ["fallbackChains"] });
        onChainSaved();
      }}
    >
      {({ values, setField, setValues, errors }) => {
        const availableProviders = providers.filter(
          (p) => p.is_active === 1 && !values.provider_ids.includes(p.id)
        );

        const addProvider = (id: string) => {
          if (id && !values.provider_ids.includes(id)) {
            setField("provider_ids", [...values.provider_ids, id]);
          }
        };

        const removeProvider = (id: string) => {
          setValues((prev) => {
            const nextTimeouts = { ...prev.provider_timeouts };
            delete nextTimeouts[id];
            return {
              ...prev,
              provider_ids: prev.provider_ids.filter((p) => p !== id),
              provider_timeouts: nextTimeouts,
            };
          });
        };

        // Blank/0/invalid clears the override (the provider then inherits the
        // chain default), so the field shows empty rather than a confusing 0.
        const setProviderTimeout = (id: string, raw: string) => {
          setValues((prev) => {
            const nextTimeouts = { ...prev.provider_timeouts };
            const n = Number(raw);
            if (raw === "" || Number.isNaN(n) || n <= 0) {
              delete nextTimeouts[id];
            } else {
              nextTimeouts[id] = n;
            }
            return { ...prev, provider_timeouts: nextTimeouts };
          });
        };

        const move = (index: number, delta: number) => {
          setValues((prev) => {
            const next = [...prev.provider_ids];
            const target = index + delta;
            if (target < 0 || target >= next.length) return prev;
            [next[index], next[target]] = [next[target], next[index]];
            return { ...prev, provider_ids: next };
          });
        };

        return (
          <>
            <FormField id="chain-name" label="Name" error={errors.name}>
              <Input
                id="chain-name"
                value={values.name}
                onChange={(e) => setField("name", e.target.value)}
                placeholder="e.g. Production failover"
              />
            </FormField>

            <FormField id="chain-description" label="Description">
              <Textarea
                id="chain-description"
                size="description"
                value={values.description}
                onChange={(e) => setField("description", e.target.value)}
                placeholder="Optional"
              />
            </FormField>

            <div className="space-y-2">
              <Label>Providers (priority order)</Label>
              <p className="text-xs text-muted-foreground">
                Tried top to bottom. The first provider is the primary; the rest
                are fallbacks used when the previous one fails.
              </p>
              {values.provider_ids.length > 0 && (
                <div className="space-y-1">
                  {values.provider_ids.map((id, index) => (
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
                        value={values.provider_timeouts[id] ?? ""}
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
                        disabled={index === values.provider_ids.length - 1}
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
              {errors.provider_ids && (
                <p className="text-sm text-red-500 mt-1">
                  {errors.provider_ids}
                </p>
              )}
            </div>

            <TooltipProvider>
              <div className="grid grid-cols-3 gap-4">
                <div className="space-y-2">
                  <div className="flex items-center gap-1.5">
                    <Label htmlFor="retry-count" className="whitespace-nowrap">
                      Retries
                    </Label>
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
                        Extra attempts for the same provider (on retryable errors
                        like timeouts, rate limits, or 5xx) before moving to the
                        next provider in the chain. Total attempts = retries + 1.
                        0 = try once, then fail over.
                      </TooltipContent>
                    </Tooltip>
                  </div>
                  <Input
                    id="retry-count"
                    type="number"
                    min={0}
                    max={10}
                    value={values.retry_count}
                    onChange={(e) =>
                      setField("retry_count", Number(e.target.value))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <div className="flex items-center gap-1.5">
                    <Label
                      htmlFor="backoff-seconds"
                      className="whitespace-nowrap"
                    >
                      Backoff (s)
                    </Label>
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
                        Seconds to wait before retrying the same provider. It
                        doubles each retry (exponential backoff): e.g. 1s → 2s →
                        4s. 0 = retry immediately with no wait.
                      </TooltipContent>
                    </Tooltip>
                  </div>
                  <Input
                    id="backoff-seconds"
                    type="number"
                    min={0}
                    max={30}
                    step={0.5}
                    value={values.backoff_seconds}
                    onChange={(e) =>
                      setField("backoff_seconds", Number(e.target.value))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <div className="flex items-center gap-1.5">
                    <Label
                      htmlFor="timeout-seconds"
                      className="whitespace-nowrap"
                    >
                      Timeout (s)
                    </Label>
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
                        If a provider takes longer than this to reply, the
                        attempt is cancelled and treated as a failure so the next
                        provider is tried. Applies to providers without their own
                        per-provider timeout set in the list above. Empty = no
                        limit.
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
                    value={values.timeout_seconds}
                    onChange={(e) =>
                      setField(
                        "timeout_seconds",
                        e.target.value === "" ? "" : Number(e.target.value)
                      )
                    }
                  />
                </div>
              </div>
            </TooltipProvider>

            <div className="flex items-center gap-2">
              <Switch
                checked={values.is_active}
                onCheckedChange={(checked) => setField("is_active", checked)}
                id="chain-active"
              />
              <Label htmlFor="chain-active">Active</Label>
            </div>
          </>
        );
      }}
    </CRUDDialog>
  );
}
