import type { ApiKey } from "@/interfaces/api-key.interface";

function parseUtc(iso: string): Date {
  return new Date(iso);
}

export function ApiKeyExpiryLines({ apiKey }: { apiKey: ApiKey }) {
  const cred = apiKey.credential_expires_at;
  const prior = apiKey.previous_hashed_expires_at;

  const credDate = cred ? parseUtc(cred) : null;
  const credExpired =
    credDate !== null && !Number.isNaN(credDate.getTime()) && credDate.getTime() <= Date.now();

  const priorDate = prior ? parseUtc(prior) : null;

  return (
    <div className="flex flex-col gap-1 text-xs text-muted-foreground">
      {credDate && !Number.isNaN(credDate.getTime()) ? (
        <span className={credExpired ? "text-destructive font-medium" : undefined}>
          {credExpired ? "Expired" : "Until"} {credDate.toLocaleString()}
        </span>
      ) : (
        <span>No expiry</span>
      )}
      {priorDate && !Number.isNaN(priorDate.getTime()) ? (
        <span>Prior until {priorDate.toLocaleString()}</span>
      ) : null}
    </div>
  );
}
