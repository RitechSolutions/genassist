import { useMemo } from "react";
import { useFeatureFlagVisible } from "@/components/featureFlag";
import { FeatureFlags } from "@/config/featureFlags";
import { WEBHOOK_TRIGGER_NODE_TYPE } from "../utils/entryNodes";

/**
 * Node types hidden from every "add node" surface (palette, canvas context
 * menu, ⌘K results) because their feature flag is off. Nodes already on a
 * canvas still render, so an existing workflow never breaks when a flag is
 * turned off.
 */
export const useHiddenNodeTypes = (): ReadonlySet<string> => {
  const showWebhookTrigger = useFeatureFlagVisible(FeatureFlags.WORKFLOW.WEBHOOK_TRIGGER);
  return useMemo(
    () => new Set<string>(showWebhookTrigger ? [] : [WEBHOOK_TRIGGER_NODE_TYPE]),
    [showWebhookTrigger]
  );
};
