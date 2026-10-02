import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getAllLLMProviders } from "@/services/llmProviders";
import type { LLMProvider } from "@/interfaces/llmProvider.interface";
import type { RunInputs } from "../../utils/promptEditorGates";
import type { ProviderFallback } from "../../utils/promptEditorResults";

export interface PromptProvidersState {
  providers: LLMProvider[];
  /** Scores every evaluation, including the ones started from the optimize side */
  activeEvalProviderId: string;
  setEvalProviderId: (id: string) => void;
  /** Writes the rewrite */
  activeOptimizeProviderId: string;
  setOptimizeProviderId: (id: string) => void;
  /** One query, so both selectors report the same unusable-list reason */
  providerStatus: RunInputs["providerStatus"];
  /** Names the provider a run was sent to when its provenance carries no model */
  fallbackFor: (providerId: string) => ProviderFallback | undefined;
}

/** The active LLM providers a run can be sent to, and the two independent selections */
export const usePromptProviders = (
  defaultProviderId?: string,
): PromptProvidersState => {
  const [evalProviderId, setEvalProviderId] = useState(defaultProviderId || "");
  const [optimizeProviderId, setOptimizeProviderId] = useState(
    defaultProviderId || "",
  );

  const providersQuery = useQuery({
    queryKey: ["llmProviders"],
    queryFn: getAllLLMProviders,
    select: (data: LLMProvider[]) => data.filter((p) => p.is_active === 1),
  });
  const providers = providersQuery.data ?? [];
  // A selection pointing at a deactivated provider must never reach a request
  const activeIdOf = (selected: string) =>
    providers.some((p) => p.id === selected) ? selected : "";

  return {
    providers,
    activeEvalProviderId: activeIdOf(evalProviderId),
    setEvalProviderId,
    activeOptimizeProviderId: activeIdOf(optimizeProviderId),
    setOptimizeProviderId,
    providerStatus: providersQuery.isPending
      ? "pending"
      : providersQuery.isError
        ? "error"
        : providers.length === 0
          ? "empty"
          : "ready",
    fallbackFor: (providerId) => {
      const provider = providers.find((p) => p.id === providerId);
      return provider
        ? {
            name: provider.name,
            llm_model_provider: provider.llm_model_provider,
            llm_model: provider.llm_model,
          }
        : undefined;
    },
  };
};
