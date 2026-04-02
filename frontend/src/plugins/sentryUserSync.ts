import * as Sentry from "@sentry/react";
import type { AuthMeResponse } from "@/services/auth";
import {
  getCurrentUserId,
  getTenantId,
} from "@/services/auth";

export function hasSentry(): boolean {
  return Boolean(import.meta.env.VITE_SENTRY_DSN);
}

/** Full user from GET /auth/me — call after a successful response. */
export function applySentryUserFromMeResponse(
  me: AuthMeResponse | null | undefined
): void {
  if (!hasSentry() || !me) return;

  const id = me.id ?? getCurrentUserId() ?? undefined;
  if (!id && !me.username) return;

  Sentry.setUser({
    id: id ?? me.username,
    username: me.username,
    email: me.email,
    ...(me.username ? { name: me.username } : {}),
  });

  const tenant = getTenantId();
  if (tenant) {
    Sentry.setTag("tenant_id", tenant);
  }
}

