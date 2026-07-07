import { apiRequest } from "@/config/api";
import {
  FallbackChain,
  FallbackChainMinimal,
} from "@/interfaces/fallbackChain.interface";

export const getAllFallbackChains = async (): Promise<FallbackChain[]> => {
  return await apiRequest<FallbackChain[]>("GET", "fallback-chains/");
};

export const getFallbackChainsMinimal = async (): Promise<
  FallbackChainMinimal[]
> => {
  return await apiRequest<FallbackChainMinimal[]>("GET", "fallback-chains/minimal");
};

export const getFallbackChain = async (
  id: string
): Promise<FallbackChain | null> => {
  return await apiRequest<FallbackChain>("GET", `fallback-chains/${id}`);
};

export const createFallbackChain = async (
  data: Omit<FallbackChain, "id" | "created_at" | "updated_at">
): Promise<FallbackChain> => {
  return await apiRequest<FallbackChain>(
    "POST",
    "fallback-chains",
    JSON.parse(JSON.stringify(data))
  );
};

export const updateFallbackChain = async (
  id: string,
  data: Partial<Omit<FallbackChain, "id" | "created_at" | "updated_at">>
): Promise<FallbackChain> => {
  return await apiRequest<FallbackChain>(
    "PATCH",
    `fallback-chains/${id}`,
    JSON.parse(JSON.stringify(data))
  );
};

export const deleteFallbackChain = async (id: string): Promise<void> => {
  await apiRequest<void>("DELETE", `fallback-chains/${id}`);
};
