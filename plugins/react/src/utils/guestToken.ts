/** Reads the guest token (a JWT) without verifying it; the server stays the authority. */

function decodeBase64Url(segment: string): string {
  const base64 = segment.replace(/-/g, "+").replace(/_/g, "/");
  const paddingLength = (4 - (base64.length % 4)) % 4;
  return atob(base64 + "=".repeat(paddingLength));
}

/** Expiry of the token in seconds since the epoch, or null when it cannot be read. */
export function readTokenExpirySeconds(token: string): number | null {
  const payloadSegment = token.split(".")[1];
  if (!payloadSegment) return null;
  try {
    const payload = JSON.parse(decodeBase64Url(payloadSegment));
    return typeof payload?.exp === "number" ? payload.exp : null;
  } catch {
    return null;
  }
}

/** True only when the token carries an expiry that has passed; unreadable tokens are left to the server. */
export function isGuestTokenExpired(token: string, nowMs: number = Date.now()): boolean {
  const expirySeconds = readTokenExpirySeconds(token);
  if (expirySeconds === null) return false;
  return expirySeconds * 1000 <= nowMs;
}
