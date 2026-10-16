/** Server creation time in milliseconds carried by a UUIDv7 id, or null for other id formats. */
export function readUuidV7TimeMs(id: string): number | null {
  const hex = id.replace(/-/g, "");
  const isUuidV7 = /^[0-9a-f]{32}$/i.test(hex) && hex[12] === "7";
  return isUuidV7 ? parseInt(hex.slice(0, 12), 16) : null;
}

/** How far the server clock is ahead of this device, measured from an id the server has just created. */
export function measureClockOffsetMs(serverCreatedId: string, receivedAtMs: number = Date.now()): number {
  const serverTimeMs = readUuidV7TimeMs(serverCreatedId);
  return serverTimeMs === null ? 0 : serverTimeMs - receivedAtMs;
}
