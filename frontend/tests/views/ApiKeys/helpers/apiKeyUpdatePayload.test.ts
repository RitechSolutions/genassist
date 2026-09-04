import { describe, expect, it } from "vitest";
import {
  KEEP_EXPIRY_VALUE,
  buildApiKeyUpdatePayload,
} from "@/views/ApiKeys/helpers/apiKeyUpdatePayload";

const base = { name: "renamed", is_active: true, role_ids: ["r1"] };

describe("buildApiKeyUpdatePayload", () => {
  it("omits expires_in_days when the expiry is kept", () => {
    const payload = buildApiKeyUpdatePayload({
      ...base,
      expiry_preset: KEEP_EXPIRY_VALUE,
    });
    expect(payload).toEqual({ name: "renamed", is_active: 1, role_ids: ["r1"] });
    expect(payload).not.toHaveProperty("expires_in_days");
    expect(payload).not.toHaveProperty("user_id");
  });

  it("sends 0 for Never and the day count for a duration", () => {
    expect(
      buildApiKeyUpdatePayload({ ...base, expiry_preset: "never" })
        .expires_in_days
    ).toBe(0);
    expect(
      buildApiKeyUpdatePayload({ ...base, expiry_preset: "90" }).expires_in_days
    ).toBe(90);
  });

  it("maps the active switch to 0/1 and passes roles through", () => {
    const payload = buildApiKeyUpdatePayload({
      ...base,
      is_active: false,
      role_ids: [],
      expiry_preset: KEEP_EXPIRY_VALUE,
    });
    expect(payload.is_active).toBe(0);
    expect(payload.role_ids).toEqual([]);
  });

  it.each(["", "unknown", "abc-30"])(
    "rejects an unrecognised expiry %j instead of clearing it",
    (preset) => {
      expect(() =>
        buildApiKeyUpdatePayload({ ...base, expiry_preset: preset })
      ).toThrow("Invalid expiry selection.");
    }
  );
});
