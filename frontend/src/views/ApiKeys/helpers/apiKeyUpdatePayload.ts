import type { ApiKey } from "@/interfaces/api-key.interface";
import { presetToExpiresInDays } from "@/components/api-keys/apiKeyExpiryPresets";

/** Edit-only expiry choice */
export const KEEP_EXPIRY_VALUE = "__keep__";

export type ApiKeyDialogFormValues = {
  name: string;
  is_active: boolean;
  role_ids: string[];
  expiry_preset: string;
};

/** Builds the PATCH body for an edit; expiry is only sent when the user changed it. */
export function buildApiKeyUpdatePayload(
  values: ApiKeyDialogFormValues
): Partial<ApiKey> {
  const payload: Partial<ApiKey> = {
    name: values.name,
    is_active: values.is_active ? 1 : 0,
    role_ids: values.role_ids,
  };
  if (values.expiry_preset === "never") {
    // 0 clears the stored expiry; a duration restarts it from now.
    payload.expires_in_days = 0;
  } else if (values.expiry_preset !== KEEP_EXPIRY_VALUE) {
    const days = presetToExpiresInDays(values.expiry_preset);
    if (days === undefined) {
      throw new Error("Invalid expiry selection.");
    }
    payload.expires_in_days = days;
  }
  return payload;
}
