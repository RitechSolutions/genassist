import { describe, expect, it } from "vitest";
import type { ApiKey } from "@/interfaces/api-key.interface";
import { buildApiKeyUpdatePayload } from "@/views/ApiKeys/helpers/apiKeyUpdatePayload";

const base = { name: "renamed", is_active: true, role_ids: ["r1"] };
const edited = {
  id: "k1",
  role_ids: ["r1"],
  credential_expiry_days: 90,
} as unknown as ApiKey;
const neverExpires = { id: "k1", role_ids: ["r1"] } as unknown as ApiKey;

describe("buildApiKeyUpdatePayload", () => {
  it("omits expires_in_days when the preset still matches the stored expiry", () => {
    const payload = buildApiKeyUpdatePayload(
      { ...base, expiry_preset: "90" },
      edited
    );
    expect(payload).toEqual({ name: "renamed", is_active: 1 });
    expect(payload).not.toHaveProperty("user_id");

    expect(
      buildApiKeyUpdatePayload({ ...base, expiry_preset: "never" }, neverExpires)
    ).not.toHaveProperty("expires_in_days");
  });

  it("sends 0 for Never and the day count for a duration", () => {
    expect(
      buildApiKeyUpdatePayload({ ...base, expiry_preset: "never" }, edited)
        .expires_in_days
    ).toBe(0);
    expect(
      buildApiKeyUpdatePayload({ ...base, expiry_preset: "30" }, edited)
        .expires_in_days
    ).toBe(30);
    expect(
      buildApiKeyUpdatePayload({ ...base, expiry_preset: "90" }, neverExpires)
        .expires_in_days
    ).toBe(90);
  });

  it("maps the active switch to 0/1 and sends a changed role selection", () => {
    const payload = buildApiKeyUpdatePayload(
      {
        ...base,
        is_active: false,
        role_ids: [],
        expiry_preset: "90",
      },
      edited
    );
    expect(payload.is_active).toBe(0);
    expect(payload.role_ids).toEqual([]);
  });

  it("omits role_ids when the selection is unchanged, whatever its order", () => {
    const payload = buildApiKeyUpdatePayload(
      { ...base, role_ids: ["r2", "r1"], expiry_preset: "never" },
      { id: "k1", roles: [{ id: "r1" }, { id: "r2" }] } as unknown as ApiKey
    );
    expect(payload).not.toHaveProperty("role_ids");
  });

  it.each(["", "unknown", "abc-30"])(
    "rejects an unrecognised expiry %j instead of clearing it",
    (preset) => {
      expect(() =>
        buildApiKeyUpdatePayload({ ...base, expiry_preset: preset }, edited)
      ).toThrow("Invalid expiry selection.");
    }
  );
});
