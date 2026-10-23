import type { ApiKey } from "@/interfaces/api-key.interface";
import { presetToExpiresInDays } from "@/components/api-keys/apiKeyExpiryPresets";

export type ApiKeyDialogFormValues = {
  name: string;
  is_active: boolean;
  role_ids: string[];
  expiry_preset: string;
};

/** Role ids already on a key, from whichever shape the API returned. */
export function apiKeyRoleIds(apiKey: ApiKey): string[] {
  return apiKey.roles?.map((role) => role.id) || apiKey.role_ids || [];
}

/** Expiry preset a key currently stores; no stored expiry reads as "never". */
export function apiKeyExpiryPreset(apiKey: ApiKey): string {
  const days = apiKey.credential_expiry_days;
  return typeof days === "number" && days > 0 ? String(days) : "never";
}

const sameRoleSelection = (selected: string[], current: string[]) => {
  const currentIds = new Set(current);
  return (
    selected.length === current.length &&
    selected.every((id) => currentIds.has(id))
  );
};

/** Builds the PATCH body for an edit; expiry and roles are only sent when the user changed them. */
export function buildApiKeyUpdatePayload(
  values: ApiKeyDialogFormValues,
  apiKeyToEdit: ApiKey
): Partial<ApiKey> {
  const payload: Partial<ApiKey> = {
    name: values.name,
    is_active: values.is_active ? 1 : 0,
  };

  // The picker only lists the caller's own roles, and the backend rejects role ids the caller
  // does not hold: resend the selection only when it changed.
  if (!sameRoleSelection(values.role_ids, apiKeyRoleIds(apiKeyToEdit))) {
    payload.role_ids = values.role_ids;
  }

  // Sending expires_in_days restarts the deadline from now, so an untouched preset is omitted.
  if (values.expiry_preset !== apiKeyExpiryPreset(apiKeyToEdit)) {
    if (values.expiry_preset === "never") {
      // 0 clears the stored expiry.
      payload.expires_in_days = 0;
    } else {
      const days = presetToExpiresInDays(values.expiry_preset);
      if (days === undefined) {
        throw new Error("Invalid expiry selection.");
      }
      payload.expires_in_days = days;
    }
  }
  return payload;
}
