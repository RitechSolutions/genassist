import { describe, expect, it } from "vitest";
import {
  parseFeatureFlags,
  isFeatureEnabled,
  getFeatureValue,
} from "@/helpers/featureFlag";
import {
  FeatureFlag,
  FeatureToggleAttribute,
} from "@/interfaces/featureFlag.interface";

const flag = (over: Partial<FeatureFlag>): FeatureFlag => ({
  key: "k",
  val: "true",
  description: "",
  is_active: 1,
  ...over,
});

describe("parseFeatureFlags", () => {
  it("maps a boolean 'visible' value with no prefix", () => {
    expect(parseFeatureFlags([flag({ key: "a", val: "true" })])).toEqual([
      { itemName: "a", fullKey: "a", visible: true },
    ]);
  });

  it("drops inactive flags", () => {
    expect(parseFeatureFlags([flag({ key: "a", is_active: 0 })])).toEqual([]);
  });

  it("filters by prefix and strips it from the item name", () => {
    const result = parseFeatureFlags(
      [
        flag({ key: "ui.menu.dashboard", val: "true" }),
        flag({ key: "other.thing", val: "true" }),
      ],
      "ui.menu"
    );
    expect(result).toEqual([
      { itemName: "dashboard", fullKey: "ui.menu.dashboard", visible: true },
    ]);
  });

  it("parses attribute-typed flags", () => {
    expect(
      parseFeatureFlags([
        flag({
          key: "f",
          val: "false",
          attribute: FeatureToggleAttribute.VISIBLE,
        }),
      ])
    ).toEqual([{ itemName: "f", fullKey: "f", visible: false }]);

    expect(
      parseFeatureFlags([
        flag({
          key: "f",
          val: "true",
          attribute: FeatureToggleAttribute.DISABLED,
        }),
      ])
    ).toEqual([{ itemName: "f", fullKey: "f", disabled: true }]);

    expect(
      parseFeatureFlags([
        flag({
          key: "f",
          val: "blue",
          attribute: FeatureToggleAttribute.VARIANT,
        }),
      ])
    ).toEqual([{ itemName: "f", fullKey: "f", variant: "blue" }]);
  });

  it("merges multiple attributes for the same item", () => {
    const result = parseFeatureFlags([
      flag({ key: "btn", val: "true", attribute: FeatureToggleAttribute.VISIBLE }),
      flag({ key: "btn", val: "red", attribute: FeatureToggleAttribute.VARIANT }),
    ]);
    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({
      itemName: "btn",
      visible: true,
      variant: "red",
    });
  });
});

describe("isFeatureEnabled", () => {
  it("reads an exact default flag", () => {
    expect(isFeatureEnabled([flag({ key: "a.b", val: "true" })], "a.b")).toBe(
      true
    );
    expect(isFeatureEnabled([flag({ key: "a.b", val: "false" })], "a.b")).toBe(
      false
    );
  });

  it("inverts a 'disabled' attribute", () => {
    expect(
      isFeatureEnabled(
        [
          flag({
            key: "a.b",
            val: "true",
            attribute: FeatureToggleAttribute.DISABLED,
          }),
        ],
        "a.b"
      )
    ).toBe(false);
  });

  it("falls back to an active parent flag", () => {
    expect(
      isFeatureEnabled([flag({ key: "a", val: "true" })], "a.b.c")
    ).toBe(true);
  });

  it("defaults to true when no flag matches", () => {
    expect(isFeatureEnabled([], "x.y")).toBe(true);
    expect(
      isFeatureEnabled([flag({ key: "a.b", val: "false", is_active: 0 })], "a.b")
    ).toBe(true);
  });
});

describe("getFeatureValue", () => {
  it("returns the exact flag value", () => {
    expect(getFeatureValue([flag({ key: "a", val: "x" })], "a")).toBe("x");
  });

  it("falls back to a parent value", () => {
    expect(getFeatureValue([flag({ key: "a", val: "p" })], "a.b")).toBe("p");
  });

  it("returns null when nothing matches", () => {
    expect(getFeatureValue([], "a")).toBeNull();
  });
});
