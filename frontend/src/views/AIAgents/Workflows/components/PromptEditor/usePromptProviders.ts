import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getAllLLMProviders } from "@/services/llmProviders";
import type { LLMProvider } from "@/interfaces/llmProvider.interface";
import type { RunInputs } from "../../utils/promptEditorGates";
import type { ProviderFallback } from "../../utils/promptEditorResults";

export interface PromptProvidersState {
  providers: LLMProvider[];
  /** Empty when nothing is selected or the selection is no longer active */
  activeProviderId: string;
  setSelectedProviderId: (id: string) => void;
  providerStatus: RunInputs["providerStatus"];
  /** Names the selected provider when a run's own provenance carries no model */
  providerFallback: ProviderFallback | undefined;
}

/** The active LLM providers a run can be sent to, plus the current selection */
export const usePromptProviders = (
  defaultProviderId?: string,
): PromptProvidersState => {
  const [selectedProviderId, setSelectedProviderId] = useState(
    defaultProviderId || "",
  );

  const providersQuery = useQuery({
    queryKey: ["llmProviders"],
    queryFn: getAllLLMProviders,
    select: (data: LLMProvider[]) => data.filter((p) => p.is_active === 1),
  });
  const providers = providersQuery.data ?? [];
  // A default pointing at a deactivated provider must never reach a request
  const activeProviderId = providers.some((p) => p.id === selectedProviderId)
    ? selectedProviderId
    : "";
  const activeProvider = providers.find((p) => p.id === activeProviderId);

  return {
    providers,
    activeProviderId,
    setSelectedProviderId,
    providerStatus: providersQuery.isPending
      ? "pending"
      : providersQuery.isError
        ? "error"
        : providers.length === 0
          ? "empty"
          : "ready",
    providerFallback: activeProvider
      ? {
          name: activeProvider.name,
          llm_model_provider: activeProvider.llm_model_provider,
          llm_model: activeProvider.llm_model,
        }
      : undefined,
  };
};
