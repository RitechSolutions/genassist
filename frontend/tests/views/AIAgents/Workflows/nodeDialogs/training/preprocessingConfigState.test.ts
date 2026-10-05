import { describe, it, expect } from "vitest";
import {
  BASE_PYTHON_TEMPLATE,
  ChangeDtypeStepConfig,
  PreprocessingConfig,
  RemoveDuplicatesStepConfig,
  generatePythonCodeFromConfig,
} from "@/views/AIAgents/Workflows/nodeDialogs/training/preprocessingConfig";
import {
  generatedSectionMatchesConfig,
  hasUnsavedHandEdits,
  loadPreprocessingConfig,
} from "@/views/AIAgents/Workflows/nodeDialogs/training/preprocessingConfigState";

const config: PreprocessingConfig = {
  steps: [
    {
      id: "step_1",
      type: "remove_duplicates",
      enabled: true,
      config: { subsetColumns: ["email"], keep: "last" } as RemoveDuplicatesStepConfig,
    },
    {
      id: "step_2",
      type: "change_dtype",
      enabled: false,
      config: { conversions: [{ columnName: "age", dtype: "int" }] } as ChangeDtypeStepConfig,
    },
  ],
};
const code = generatePythonCodeFromConfig(config, BASE_PYTHON_TEMPLATE);

describe("loadPreprocessingConfig (DP-7)", () => {
  it("uses the stored steps without reading the code", () => {
    // Code that would parse to nothing - the stored steps still win.
    const loaded = loadPreprocessingConfig({ pythonCode: "garbage", preprocessingConfig: config });
    expect(loaded.source).toBe("stored");
    expect(loaded.config).toEqual(config);
  });

  it("returns a copy, so editing steps never mutates the saved node data", () => {
    const loaded = loadPreprocessingConfig({ pythonCode: code, preprocessingConfig: config });
    (loaded.config.steps[0].config as RemoveDuplicatesStepConfig).keep = "first";
    expect((config.steps[0].config as RemoveDuplicatesStepConfig).keep).toBe("last");
  });

  it("reads an older node (no stored steps) from its code once", () => {
    const loaded = loadPreprocessingConfig({ pythonCode: code });
    expect(loaded.source).toBe("migrated");
    expect(loaded.config).toEqual(config);
  });

  it("starts empty for a new node", () => {
    expect(loadPreprocessingConfig({})).toEqual({ config: { steps: [] }, source: "empty" });
  });

  it("keeps steps whose details the code can't express - e.g. a typed column name", () => {
    // A name that a hand-edited/older code form could garble survives intact,
    // because it's never re-read from code.
    const tricky: PreprocessingConfig = {
      steps: [
        {
          id: "s",
          type: "change_dtype",
          enabled: true,
          config: {
            conversions: [{ columnName: '# STEP_END:s:change_dtype "x"', dtype: "float" }],
          } as ChangeDtypeStepConfig,
        },
      ],
    };
    const trickyCode = generatePythonCodeFromConfig(tricky, BASE_PYTHON_TEMPLATE);
    expect(loadPreprocessingConfig({ pythonCode: trickyCode, preprocessingConfig: tricky }).config).toEqual(tricky);
  });
});

describe("hand edits to the generated function (DP-7)", () => {
  it("generated code matches its steps", () => {
    expect(generatedSectionMatchesConfig(code, config)).toBe(true);
  });

  it("the untouched template of a new node counts as matching", () => {
    expect(generatedSectionMatchesConfig(BASE_PYTHON_TEMPLATE, { steps: [] })).toBe(true);
  });

  it("an edit inside the generated function is detected", () => {
    const edited = code.replace("df = df.copy()", "df = df.copy()\n    df = df.head(10)");
    expect(generatedSectionMatchesConfig(edited, config)).toBe(false);
    expect(hasUnsavedHandEdits(edited, config, code)).toBe(true);
  });

  it("an edit outside the generated function is not a hand edit", () => {
    const edited = code.replace("#Write your code here", "#Write your code here\n    df['x'] = 1");
    expect(hasUnsavedHandEdits(edited, config, code)).toBe(false);
  });

  it("an older node's differently-generated code is not flagged until it changes", () => {
    // Same steps, code from an earlier generator version (different wording).
    const olderCode = code.replace("# Remove duplicate rows", "# remove dupes (old generator)");
    expect(generatedSectionMatchesConfig(olderCode, config)).toBe(false);
    expect(hasUnsavedHandEdits(olderCode, config, olderCode)).toBe(false);
  });
});
