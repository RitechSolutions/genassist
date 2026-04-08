/**
 * Client-side only: decode JWT payload (no signature check) to help set MCP inbound OAuth fields.
 * Never send the token to the backend from this helper — use only in the browser.
 */

export type InboundOAuthJwtHints = {
  /** Full OIDC issuer URL derived from the token `iss` claim */
  issuerUrl: string;
  clientIdHint?: string;
  /** Space-separated scopes from the token `scope` claim, if present */
  scopeHint?: string;
};

function normalizeIssuerLikeBackend(iss: string): string {
  return iss.trim().replace(/\/+$/, "");
}

/**
 * Parse a JWT access token payload and return issuer URL (iss + well-known path), optional client id and scope.
 * Returns null if not a JWT or missing iss.
 */
export function extractInboundOAuthHintsFromJwt(token: string): InboundOAuthJwtHints | null {
  const raw = token.trim();
  const parts = raw.split(".");
  if (parts.length !== 3 || !parts[1]) {
    return null;
  }

  let payloadJson: string;
  try {
    const b64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const pad = b64.length % 4;
    const padded = pad ? b64 + "=".repeat(4 - pad) : b64;
    payloadJson = atob(padded);
  } catch {
    return null;
  }

  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(payloadJson);
  } catch {
    return null;
  }

  const issRaw = payload["iss"];
  if (typeof issRaw !== "string" || !issRaw.trim()) {
    return null;
  }
  const issuer = normalizeIssuerLikeBackend(issRaw);
  const issuerUrl = `${issuer}/.well-known/openid-configuration`;

  const azp = payload["azp"];
  const clientId = payload["client_id"];
  const appid = payload["appid"];
  let clientIdHint: string | undefined;
  if (typeof azp === "string" && azp.trim()) {
    clientIdHint = azp.trim();
  } else if (typeof clientId === "string" && clientId.trim()) {
    clientIdHint = clientId.trim();
  } else if (typeof appid === "string" && appid.trim()) {
    clientIdHint = appid.trim();
  }

  const scopeRaw = payload["scope"];
  let scopeHint: string | undefined;
  if (typeof scopeRaw === "string" && scopeRaw.trim()) {
    scopeHint = scopeRaw.trim();
  }

  return { issuerUrl, clientIdHint, scopeHint };
}
