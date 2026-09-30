import { describe, it, expect } from "vitest";
import {
  BASE_PYTHON_TEMPLATE,
  ChangeDtypeStepConfig,
  DropColumnOrRowStepConfig,
  DropHighNullColumnsStepConfig,
  PreprocessingConfig,
  RemoveDuplicatesStepConfig,
  generatePythonCodeFromConfig,
  parsePythonCodeToConfig,
  createPreprocessingStep,
  getStepTypeDisplayName,
} from "@/views/AIAgents/Workflows/nodeDialogs/training/preprocessingConfig";

describe("preprocessingConfig - new operations", () => {
  it("remove_duplicates: generates drop_duplicates code and round-trips", () => {
    const config: PreprocessingConfig = {
      steps: [
        {
          id: "step_1",
          type: "remove_duplicates",
          enabled: true,
          config: {
            subsetColumns: ["email", "name"],
            keep: "last",
          } as RemoveDuplicatesStepConfig,
        },
      ],
    };

    const code = generatePythonCodeFromConfig(config, BASE_PYTHON_TEMPLATE);
    expect(code).toContain('df.drop_duplicates(subset=["email", "name"], keep="last")');

    const parsed = parsePythonCodeToConfig(code);
    expect(parsed.steps).toHaveLength(1);
    expect(parsed.steps[0].type).toBe("remove_duplicates");
    expect(parsed.steps[0].config).toEqual({
      subsetColumns: ["email", "name"],
      keep: "last",
    });
  });

  it("remove_duplicates: with no subset compares all columns", () => {
    const config: PreprocessingConfig = {
      steps: [
        {
          id: "step_1",
          type: "remove_duplicates",
          enabled: true,
          config: { subsetColumns: [], keep: "first" } as RemoveDuplicatesStepConfig,
        },
      ],
    };
    const code = generatePythonCodeFromConfig(config, BASE_PYTHON_TEMPLATE);
    expect(code).toContain('df.drop_duplicates(keep="first")');
    expect(code).not.toContain("subset=");
  });

  it("drop_column_or_row: column mode generates df.drop(columns=...) and round-trips", () => {
    const config: PreprocessingConfig = {
      steps: [
        {
          id: "step_1",
          type: "drop_column_or_row",
          enabled: true,
          config: {
            target: "column",
            columns: ["legacy_id", "notes"],
            rowIndices: [],
          } as DropColumnOrRowStepConfig,
        },
      ],
    };

    const code = generatePythonCodeFromConfig(config, BASE_PYTHON_TEMPLATE);
    expect(code).toContain('df.drop(columns=["legacy_id", "notes"], errors="ignore")');

    const parsed = parsePythonCodeToConfig(code);
    expect(parsed.steps[0].config).toEqual({
      target: "column",
      columns: ["legacy_id", "notes"],
      rowIndices: [],
    });
  });

  it("drop_column_or_row: row mode generates df.drop(index=...) and round-trips", () => {
    const config: PreprocessingConfig = {
      steps: [
        {
          id: "step_1",
          type: "drop_column_or_row",
          enabled: true,
          config: {
            target: "row",
            columns: [],
            rowIndices: [0, 5, 12],
          } as DropColumnOrRowStepConfig,
        },
      ],
    };

    const code = generatePythonCodeFromConfig(config, BASE_PYTHON_TEMPLATE);
    expect(code).toContain('df.drop(index=[0, 5, 12], errors="ignore")');

    const parsed = parsePythonCodeToConfig(code);
    expect(parsed.steps[0].config).toEqual({
      target: "row",
      columns: [],
      rowIndices: [0, 5, 12],
    });
  });

  it("drop_high_null_columns: generates a null-percentage filter and round-trips", () => {
    const config: PreprocessingConfig = {
      steps: [
        {
          id: "step_1",
          type: "drop_high_null_columns",
          enabled: true,
          config: { thresholdPercent: 80 } as DropHighNullColumnsStepConfig,
        },
      ],
    };

    const code = generatePythonCodeFromConfig(config, BASE_PYTHON_TEMPLATE);
    expect(code).toContain("df = df.loc[:, df.isnull().mean() * 100 <= 80]");

    const parsed = parsePythonCodeToConfig(code);
    expect(parsed.steps[0].config).toEqual({ thresholdPercent: 80 });
  });

  it("change_dtype: numeric astype generates code and round-trips", () => {
    const config: PreprocessingConfig = {
      steps: [
        {
          id: "step_1",
          type: "change_dtype",
          enabled: true,
          config: { columnName: "age", dtype: "int" } as ChangeDtypeStepConfig,
        },
      ],
    };

    const code = generatePythonCodeFromConfig(config, BASE_PYTHON_TEMPLATE);
    expect(code).toContain('df["age"] = df["age"].astype("int64")');

    const parsed = parsePythonCodeToConfig(code);
    expect(parsed.steps[0].config).toEqual({ columnName: "age", dtype: "int" });
  });

  it("change_dtype: datetime uses pd.to_datetime and round-trips", () => {
    const config: PreprocessingConfig = {
      steps: [
        {
          id: "step_1",
          type: "change_dtype",
          enabled: true,
          config: { columnName: "created_at", dtype: "datetime" } as ChangeDtypeStepConfig,
        },
      ],
    };

    const code = generatePythonCodeFromConfig(config, BASE_PYTHON_TEMPLATE);
    expect(code).toContain(
      'df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")'
    );

    const parsed = parsePythonCodeToConfig(code);
    expect(parsed.steps[0].config).toEqual({
      columnName: "created_at",
      dtype: "datetime",
    });
  });

  it("createPreprocessingStep gives each new type a sensible default config", () => {
    expect(createPreprocessingStep("remove_duplicates").config).toEqual({
      subsetColumns: [],
      keep: "first",
    });
    expect(createPreprocessingStep("drop_column_or_row").config).toEqual({
      target: "column",
      columns: [],
      rowIndices: [],
    });
    expect(createPreprocessingStep("drop_high_null_columns").config).toEqual({
      thresholdPercent: 80,
    });
    expect(createPreprocessingStep("change_dtype").config).toEqual({
      columnName: "",
      dtype: "string",
    });
  });

  it("getStepTypeDisplayName returns a label for each new type", () => {
    expect(getStepTypeDisplayName("remove_duplicates")).toBe("Remove Duplicate Rows");
    expect(getStepTypeDisplayName("drop_column_or_row")).toBe("Remove Column/Row");
    expect(getStepTypeDisplayName("drop_high_null_columns")).toBe(
      "Remove High-Null Columns"
    );
    expect(getStepTypeDisplayName("change_dtype")).toBe("Change Column Data Type");
  });

  it("multiple new steps chain together in one generated function", () => {
    const config: PreprocessingConfig = {
      steps: [
        {
          id: "step_1",
          type: "remove_duplicates",
          enabled: true,
          config: { subsetColumns: [], keep: "first" } as RemoveDuplicatesStepConfig,
        },
        {
          id: "step_2",
          type: "drop_high_null_columns",
          enabled: true,
          config: { thresholdPercent: 50 } as DropHighNullColumnsStepConfig,
        },
        {
          id: "step_3",
          type: "change_dtype",
          enabled: true,
          config: { columnName: "score", dtype: "float" } as ChangeDtypeStepConfig,
        },
      ],
    };

    const code = generatePythonCodeFromConfig(config, BASE_PYTHON_TEMPLATE);
    const parsed = parsePythonCodeToConfig(code);

    expect(parsed.steps.map((s) => s.type)).toEqual([
      "remove_duplicates",
      "drop_high_null_columns",
      "change_dtype",
    ]);
    expect(parsed.steps[1].config).toEqual({ thresholdPercent: 50 });
    expect(parsed.steps[2].config).toEqual({ columnName: "score", dtype: "float" });
  });
});
