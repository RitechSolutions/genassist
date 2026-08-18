import { describe, expect, it } from "vitest";
import { extractInboundOAuthHintsFromJwt } from "@/helpers/mcpOauthInboundJwt";

// Encode an object as a base64url JWT payload segment.
function base64UrlPayload(payload: unknown): string {
  return Buffer.from(JSON.stringify(payload))
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

// Build a fake "header.payload.signature" JWT from a payload object.
function makeJwt(payload: unknown): string {
  return `header.${base64UrlPayload(payload)}.signature`;
}

describe("extractInboundOAuthHintsFromJwt", () => {
  it("derives the well-known issuer URL from the iss claim", () => {
    const token = makeJwt({ iss: "https://issuer.example.com" });
    expect(extractInboundOAuthHintsFromJwt(token)).toEqual({
      issuerUrl: "https://issuer.example.com/.well-known/openid-configuration",
      clientIdHint: undefined,
      scopeHint: undefined,
    });
  });

  it("normalizes the issuer by trimming whitespace and trailing slashes", () => {
    const token = makeJwt({ iss: "  https://issuer.example.com///  " });
    const result = extractInboundOAuthHintsFromJwt(token);
    expect(result?.issuerUrl).toBe(
      "https://issuer.example.com/.well-known/openid-configuration",
    );
  });

  it("prefers azp for the client id hint", () => {
    const token = makeJwt({
      iss: "https://issuer.example.com",
      azp: "azp-client",
      client_id: "cid-client",
      appid: "appid-client",
    });
    expect(extractInboundOAuthHintsFromJwt(token)?.clientIdHint).toBe(
      "azp-client",
    );
  });

  it("falls back to client_id when azp is missing/blank", () => {
    const token = makeJwt({
      iss: "https://issuer.example.com",
      azp: "   ",
      client_id: "cid-client",
      appid: "appid-client",
    });
    expect(extractInboundOAuthHintsFromJwt(token)?.clientIdHint).toBe(
      "cid-client",
    );
  });

  it("falls back to appid when azp and client_id are absent", () => {
    const token = makeJwt({
      iss: "https://issuer.example.com",
      appid: "appid-client",
    });
    expect(extractInboundOAuthHintsFromJwt(token)?.clientIdHint).toBe(
      "appid-client",
    );
  });

  it("trims the client id hint", () => {
    const token = makeJwt({
      iss: "https://issuer.example.com",
      azp: "  azp-client  ",
    });
    expect(extractInboundOAuthHintsFromJwt(token)?.clientIdHint).toBe(
      "azp-client",
    );
  });

  it("leaves clientIdHint undefined when none of azp/client_id/appid are usable strings", () => {
    const token = makeJwt({
      iss: "https://issuer.example.com",
      azp: 123,
      client_id: "",
      appid: "   ",
    });
    expect(extractInboundOAuthHintsFromJwt(token)?.clientIdHint).toBeUndefined();
  });

  it("extracts and trims the scope claim", () => {
    const token = makeJwt({
      iss: "https://issuer.example.com",
      scope: "  read write  ",
    });
    expect(extractInboundOAuthHintsFromJwt(token)?.scopeHint).toBe("read write");
  });

  it("leaves scopeHint undefined for blank or non-string scope", () => {
    expect(
      extractInboundOAuthHintsFromJwt(
        makeJwt({ iss: "https://issuer.example.com", scope: "   " }),
      )?.scopeHint,
    ).toBeUndefined();
    expect(
      extractInboundOAuthHintsFromJwt(
        makeJwt({ iss: "https://issuer.example.com", scope: ["read"] }),
      )?.scopeHint,
    ).toBeUndefined();
  });

  it("trims surrounding whitespace on the whole token", () => {
    const token = `  ${makeJwt({ iss: "https://issuer.example.com" })}  `;
    expect(extractInboundOAuthHintsFromJwt(token)?.issuerUrl).toBe(
      "https://issuer.example.com/.well-known/openid-configuration",
    );
  });

  it("returns null when the token does not have exactly three segments", () => {
    expect(extractInboundOAuthHintsFromJwt("abc")).toBeNull();
    expect(extractInboundOAuthHintsFromJwt("a.b")).toBeNull();
    expect(extractInboundOAuthHintsFromJwt("a.b.c.d")).toBeNull();
  });

  it("returns null when the payload segment is empty", () => {
    expect(extractInboundOAuthHintsFromJwt("a..c")).toBeNull();
  });

  it("returns null when the payload is not valid JSON", () => {
    const notJson = Buffer.from("not json at all")
      .toString("base64")
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");
    expect(extractInboundOAuthHintsFromJwt(`header.${notJson}.sig`)).toBeNull();
  });

  it("returns null when base64 decoding fails on invalid characters", () => {
    expect(extractInboundOAuthHintsFromJwt("header.@@@@.sig")).toBeNull();
  });

  it("returns null when iss is missing", () => {
    expect(
      extractInboundOAuthHintsFromJwt(makeJwt({ scope: "read" })),
    ).toBeNull();
  });

  it("returns null when iss is not a non-empty string", () => {
    expect(extractInboundOAuthHintsFromJwt(makeJwt({ iss: 42 }))).toBeNull();
    expect(extractInboundOAuthHintsFromJwt(makeJwt({ iss: "   " }))).toBeNull();
    expect(extractInboundOAuthHintsFromJwt(makeJwt({ iss: "" }))).toBeNull();
  });
});
