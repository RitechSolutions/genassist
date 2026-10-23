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
          config: {
            conversions: [{ columnName: "age", dtype: "int" }],
          } as ChangeDtypeStepConfig,
        },
      ],
    };

    const code = generatePythonCodeFromConfig(config, BASE_PYTHON_TEMPLATE);
    expect(code).toContain('df["age"] = df["age"].astype("Int64")');

    const parsed = parsePythonCodeToConfig(code);
    expect(parsed.steps[0].config).toEqual({
      conversions: [{ columnName: "age", dtype: "int" }],
    });
  });

  it("change_dtype: datetime uses pd.to_datetime and round-trips", () => {
    const config: PreprocessingConfig = {
      steps: [
        {
          id: "step_1",
          type: "change_dtype",
          enabled: true,
          config: {
            conversions: [{ columnName: "created_at", dtype: "datetime" }],
          } as ChangeDtypeStepConfig,
        },
      ],
    };

    const code = generatePythonCodeFromConfig(config, BASE_PYTHON_TEMPLATE);
    expect(code).toContain(
      '_parsed_dates = pd.to_datetime(df["created_at"], errors="coerce", format="mixed")'
    );

    const parsed = parsePythonCodeToConfig(code);
    expect(parsed.steps[0].config).toEqual({
      conversions: [{ columnName: "created_at", dtype: "datetime" }],
    });
  });

  it("change_dtype: multiple columns in one step generate and round-trip in order", () => {
    const config: PreprocessingConfig = {
      steps: [
        {
          id: "step_1",
          type: "change_dtype",
          enabled: true,
          config: {
            conversions: [
              { columnName: "lag_336", dtype: "float" },
              { columnName: "created_at", dtype: "datetime" },
              { columnName: "is_active", dtype: "bool" },
            ],
          } as ChangeDtypeStepConfig,
        },
      ],
    };

    const code = generatePythonCodeFromConfig(config, BASE_PYTHON_TEMPLATE);
    expect(code).toContain('df["lag_336"] = df["lag_336"].astype("float64")');
    expect(code).toContain(
      '_parsed_dates = pd.to_datetime(df["created_at"], errors="coerce", format="mixed")'
    );
    expect(code).toContain('df["is_active"] = df["is_active"].map(');
    expect(code).toContain('.astype("boolean")');

    const parsed = parsePythonCodeToConfig(code);
    expect(parsed.steps[0].config).toEqual({
      conversions: [
        { columnName: "lag_336", dtype: "float" },
        { columnName: "created_at", dtype: "datetime" },
        { columnName: "is_active", dtype: "bool" },
      ],
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
      conversions: [],
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
          config: {
            conversions: [{ columnName: "score", dtype: "float" }],
          } as ChangeDtypeStepConfig,
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
    expect(parsed.steps[2].config).toEqual({
      conversions: [{ columnName: "score", dtype: "float" }],
    });
  });

  it("change_dtype: code saved before the Int64/boolean change still parses", () => {
    const code = BASE_PYTHON_TEMPLATE.replace(
      "    # STEP_MARKER_START: Preprocessing steps will be inserted here\n    # STEP_MARKER_END\n",
      [
        "    # STEP_START:step_1:change_dtype",
        '    df["age"] = df["age"].astype("int64")',
        '    df["flag"] = df["flag"].astype("bool")',
        "    # STEP_END:step_1:change_dtype",
        "",
      ].join("\n")
    );
    expect(parsePythonCodeToConfig(code).steps[0].config).toEqual({
      conversions: [
        { columnName: "age", dtype: "int" },
        { columnName: "flag", dtype: "bool" },
      ],
    });
  });
});

describe("preprocessingConfig - bug fixes", () => {
  const roundTrip = (config: PreprocessingConfig) =>
    parsePythonCodeToConfig(generatePythonCodeFromConfig(config, BASE_PYTHON_TEMPLATE));

  it("a disabled step generates no code but survives a save/reopen round-trip", () => {
    const config: PreprocessingConfig = {
      steps: [
        {
          id: "step_1",
          type: "remove_duplicates",
          enabled: false,
          config: { subsetColumns: ["email"], keep: "last" } as RemoveDuplicatesStepConfig,
        },
        {
          id: "step_2",
          type: "drop_high_null_columns",
          enabled: true,
          config: { thresholdPercent: 50 } as DropHighNullColumnsStepConfig,
        },
      ],
    };

    const code = generatePythonCodeFromConfig(config, BASE_PYTHON_TEMPLATE);
    expect(code).not.toContain("drop_duplicates");
    expect(code).toContain("df.isnull().mean() * 100 <= 50");

    expect(parsePythonCodeToConfig(code).steps).toEqual(config.steps);
  });

  it("re-enabling a disabled step brings its code back", () => {
    const disabled = roundTrip({
      steps: [
        {
          id: "step_1",
          type: "change_dtype",
          enabled: false,
          config: { conversions: [{ columnName: "age", dtype: "float" }] } as ChangeDtypeStepConfig,
        },
      ],
    });
    const reEnabled = { steps: disabled.steps.map((s) => ({ ...s, enabled: true })) };
    expect(generatePythonCodeFromConfig(reEnabled, BASE_PYTHON_TEMPLATE)).toContain(
      'df["age"] = df["age"].astype("float64")'
    );
  });

  it("column names with quotes, backslashes, commas and brackets are escaped and round-trip", () => {
    const tricky = ['say "hi"', "C:\\path", "a, b", "x]y", "it's"];
    const config: PreprocessingConfig = {
      steps: [
        {
          id: "step_1",
          type: "remove_duplicates",
          enabled: true,
          config: { subsetColumns: tricky, keep: "first" } as RemoveDuplicatesStepConfig,
        },
        {
          id: "step_2",
          type: "drop_column_or_row",
          enabled: true,
          config: { target: "column", columns: tricky, rowIndices: [] } as DropColumnOrRowStepConfig,
        },
        {
          id: "step_3",
          type: "change_dtype",
          enabled: true,
          config: {
            conversions: tricky.map((columnName) => ({ columnName, dtype: "string" as const })),
          } as ChangeDtypeStepConfig,
        },
      ],
    };

    const code = generatePythonCodeFromConfig(config, BASE_PYTHON_TEMPLATE);
    expect(code).toContain(String.raw`"say \"hi\""`);
    expect(code).toContain(String.raw`"C:\\path"`);
    expect(parsePythonCodeToConfig(code).steps).toEqual(config.steps);
  });

  it("a newline in a column name can't break out of the generated comment", () => {
    const code = generatePythonCodeFromConfig(
      {
        steps: [
          {
            id: "step_1",
            type: "change_dtype",
            enabled: true,
            config: {
              conversions: [{ columnName: "a\nimport os", dtype: "float" }],
            } as ChangeDtypeStepConfig,
          },
        ],
      },
      BASE_PYTHON_TEMPLATE
    );
    expect(code).not.toMatch(/^\s*import os/m);
  });

  it("steps with nothing configured yet survive a round-trip with their defaults", () => {
    const config: PreprocessingConfig = {
      steps: [
        {
          id: "step_1",
          type: "change_dtype",
          enabled: true,
          config: { conversions: [] } as ChangeDtypeStepConfig,
        },
        {
          id: "step_2",
          type: "drop_column_or_row",
          enabled: true,
          config: { target: "row", columns: [], rowIndices: [] } as DropColumnOrRowStepConfig,
        },
        {
          id: "step_3",
          type: "drop_column_or_row",
          enabled: true,
          config: { target: "column", columns: [], rowIndices: [] } as DropColumnOrRowStepConfig,
        },
      ],
    };
    expect(roundTrip(config).steps).toEqual(config.steps);
  });

  it("int conversion uses nullable Int64 and bool conversion maps text values", () => {
    const code = generatePythonCodeFromConfig(
      {
        steps: [
          {
            id: "step_1",
            type: "change_dtype",
            enabled: true,
            config: {
              conversions: [
                { columnName: "age", dtype: "int" },
                { columnName: "flag", dtype: "bool" },
              ],
            } as ChangeDtypeStepConfig,
          },
        ],
      },
      BASE_PYTHON_TEMPLATE
    );
    expect(code).toContain('df["age"] = df["age"].astype("Int64")');
    expect(code).toContain(
      'df["flag"] = df["flag"].map(lambda v: v if pd.isna(v) else {"true": True, "false": False, "1": True, "0": False, "1.0": True, "0.0": False, "yes": True, "no": False}.get(str(v).strip().lower(), v)).astype("boolean")'
    );
  });

  it("datetime conversion fails on unreadable values instead of silently emptying them", () => {
    const code = generatePythonCodeFromConfig(
      {
        steps: [
          {
            id: "step_1",
            type: "change_dtype",
            enabled: true,
            config: {
              conversions: [{ columnName: "created_at", dtype: "datetime" }],
            } as ChangeDtypeStepConfig,
          },
        ],
      },
      BASE_PYTHON_TEMPLATE
    );
    expect(code).toContain('_unparsed = df["created_at"].notna() & _parsed_dates.isna()');
    expect(code).toContain("raise ValueError(");
    expect(code).toContain('df["created_at"] = _parsed_dates');
  });

  it("datetime code saved in the older one-line form still parses", () => {
    const code = BASE_PYTHON_TEMPLATE.replace(
      "    # STEP_MARKER_START: Preprocessing steps will be inserted here\n    # STEP_MARKER_END\n",
      [
        "    # STEP_START:step_1:change_dtype",
        '    df["d"] = pd.to_datetime(df["d"], errors="coerce")',
        "    # STEP_END:step_1:change_dtype",
        "",
      ].join("\n")
    );
    expect(parsePythonCodeToConfig(code).steps[0].config).toEqual({
      conversions: [{ columnName: "d", dtype: "datetime" }],
    });
  });

  it("category conversion generates astype(\"category\") and round-trips", () => {
    const config: PreprocessingConfig = {
      steps: [
        {
          id: "step_1",
          type: "change_dtype",
          enabled: true,
          config: {
            conversions: [{ columnName: "level", dtype: "category" }],
          } as ChangeDtypeStepConfig,
        },
      ],
    };
    const code = generatePythonCodeFromConfig(config, BASE_PYTHON_TEMPLATE);
    expect(code).toContain('df["level"] = df["level"].astype("category")');
    expect(parsePythonCodeToConfig(code).steps).toEqual(config.steps);
  });
});
