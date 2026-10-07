import { describe, expect, it } from "vitest";
import {
  MAX_IMPORT_FILES,
  addFiles,
  describeDroppedFiles,
  describeReadableFile,
  fileKey,
  summarizeFileImportOutcome,
  summarizePreview,
} from "@/views/TestSuites/helpers/datasetFileImport";
import type {
  DatasetFileResult,
  ImportCasesFromFilesResult,
} from "@/interfaces/testSuite.interface";

const file = (name: string, size = 10, lastModified = 1): File =>
  ({ name, size, lastModified }) as File;

const fileResult = (overrides: Partial<DatasetFileResult> = {}): DatasetFileResult => ({
  filename: "a.json",
  status: "ok",
  conversations: 0,
  turns: 0,
  duplicates: 0,
  repeated: 0,
  repeated_from: [],
  errors: [],
  ...overrides,
});

const preview = (
  overrides: Partial<ImportCasesFromFilesResult> = {},
): ImportCasesFromFilesResult => ({
  files: [],
  conversations: 0,
  turns: 0,
  duplicates: 0,
  repeated: 0,
  failed_files: 0,
  error: null,
  ...overrides,
});

describe("addFiles", () => {
  it("appends new files in the order they were picked", () => {
    const { files, dropped } = addFiles([file("a.json")], [file("b.json"), file("c.json")]);
    expect(files.map((f) => f.name)).toEqual(["a.json", "b.json", "c.json"]);
    expect(dropped).toBe(0);
  });

  it("skips a file that is already selected", () => {
    const { files } = addFiles([file("a.json")], [file("a.json")]);
    expect(files).toHaveLength(1);
  });

  it("keeps two different files that share a name", () => {
    const { files } = addFiles([file("a.json", 10)], [file("a.json", 20)]);
    expect(files).toHaveLength(2);
  });

  it("stops at the cap and counts what it left out", () => {
    const current = Array.from({ length: MAX_IMPORT_FILES - 1 }, (_, n) => file(`${n}.json`));
    const { files, dropped } = addFiles(current, [file("x.json"), file("y.json"), file("z.json")]);
    expect(files).toHaveLength(MAX_IMPORT_FILES);
    expect(files.at(-1)?.name).toBe("x.json");
    expect(dropped).toBe(2);
  });
});

describe("fileKey", () => {
  it("tells files apart by name, size and modified time", () => {
    expect(fileKey(file("a.json", 1, 1))).not.toBe(fileKey(file("a.json", 1, 2)));
  });
});

describe("describeDroppedFiles", () => {
  it("agrees for one file and for several", () => {
    expect(describeDroppedFiles(1, 20)).toBe(
      "One import takes up to 20 files, so 1 file was not added.",
    );
    expect(describeDroppedFiles(3, 20)).toBe(
      "One import takes up to 20 files, so 3 files were not added.",
    );
  });
});

describe("describeReadableFile", () => {
  const alone = (result: DatasetFileResult) => describeReadableFile(result, 0, [result]);
  // A second file whose repeats point back at the first.
  const second = (overrides: Partial<DatasetFileResult>) => {
    const files = [
      fileResult({ filename: "01.json", conversations: 6, turns: 6 }),
      fileResult({ filename: "04.json", ...overrides }),
    ];
    return describeReadableFile(files[1], 1, files);
  };

  it("says what the file adds", () => {
    expect(alone(fileResult({ conversations: 2, turns: 5 }))).toBe(
      "Adds 2 conversations (5 turns).",
    );
  });

  it("says which conversations the dataset already holds", () => {
    expect(alone(fileResult({ conversations: 1, turns: 1, duplicates: 1 }))).toBe(
      "Adds 1 conversation (1 turn). 1 conversation is already in this dataset and is skipped.",
    );
    expect(alone(fileResult({ conversations: 1, turns: 2, duplicates: 3 }))).toBe(
      "Adds 1 conversation (2 turns). 3 conversations are already in this dataset and are skipped.",
    );
  });

  it("names the other file a repeat comes from, not the dataset", () => {
    expect(second({ conversations: 1, turns: 1, repeated: 2, repeated_from: [0] })).toBe(
      "Adds 1 conversation (1 turn). 2 conversations also appear in 01.json and are skipped.",
    );
  });

  it("says when a repeat comes from earlier in the same file", () => {
    expect(alone(fileResult({ conversations: 1, turns: 1, repeated: 1, repeated_from: [0] }))).toBe(
      "Adds 1 conversation (1 turn). 1 conversation also appears earlier in this file and is skipped.",
    );
  });

  it("stops naming files once repeats come from several", () => {
    const files = [
      fileResult({ filename: "a.json", conversations: 1, turns: 1 }),
      fileResult({ filename: "b.json", conversations: 1, turns: 1 }),
      fileResult({ filename: "c.json", conversations: 1, turns: 1, repeated: 2, repeated_from: [0, 1] }),
    ];
    expect(describeReadableFile(files[2], 2, files)).toBe(
      "Adds 1 conversation (1 turn). 2 conversations also appear in other files you chose and are skipped.",
    );
  });

  it("keeps the dataset and the other files apart", () => {
    expect(
      second({ conversations: 1, turns: 1, duplicates: 1, repeated: 1, repeated_from: [0] }),
    ).toBe(
      "Adds 1 conversation (1 turn). 1 conversation is already in this dataset and is skipped. 1 conversation also appears in 01.json and is skipped.",
    );
  });

  it("groups large numbers the way the API's messages do", () => {
    expect(alone(fileResult({ conversations: 5001, turns: 12000 }))).toBe(
      "Adds 5,001 conversations (12,000 turns).",
    );
  });

  it("says when the whole file is already in the dataset", () => {
    expect(alone(fileResult({ duplicates: 4 }))).toBe(
      "Everything in this file is already in this dataset.",
    );
  });

  it("says when the whole file repeats another file", () => {
    expect(second({ repeated: 3, repeated_from: [0] })).toBe(
      "Everything in this file also appears in 01.json.",
    );
  });

  it("says when the whole file is split between the dataset and another file", () => {
    expect(second({ duplicates: 1, repeated: 1, repeated_from: [0] })).toBe(
      "Everything in this file is already in this dataset or in 01.json.",
    );
  });
});

describe("summarizePreview", () => {
  it("allows the import when something is added", () => {
    expect(summarizePreview(preview({ conversations: 3, turns: 7 }))).toEqual({
      text: "Adds 3 conversations (7 turns).",
      canImport: true,
    });
  });

  it("still allows it when some files are left out, and says so", () => {
    expect(
      summarizePreview(preview({ conversations: 1, turns: 1, failed_files: 2 })),
    ).toEqual({
      text: "Adds 1 conversation (1 turn). 2 files are left out.",
      canImport: true,
    });
  });

  it("blocks it when nothing is new", () => {
    expect(summarizePreview(preview({ duplicates: 2 }))).toEqual({
      text: "Nothing new to import.",
      canImport: false,
    });
  });

  it("blocks it with the reason the import cannot go ahead", () => {
    const error = "These files add 6,200 turns, and one import can add at most 5,000.";
    expect(summarizePreview(preview({ conversations: 9, turns: 6200, error }))).toEqual({
      text: error,
      canImport: false,
    });
  });
});

describe("summarizeFileImportOutcome", () => {
  it("names what was imported", () => {
    expect(summarizeFileImportOutcome(preview({ conversations: 2, turns: 3 }))).toEqual({
      ok: true,
      message: "Imported 2 conversations (3 turns).",
    });
  });

  it("mentions skipped conversations", () => {
    expect(
      summarizeFileImportOutcome(preview({ conversations: 1, turns: 1, duplicates: 1 })),
    ).toEqual({
      ok: true,
      message: "Imported 1 conversation (1 turn). Skipped 1 conversation already in the dataset.",
    });
  });

  it("tells repeats across files apart from the dataset", () => {
    expect(
      summarizeFileImportOutcome(preview({ conversations: 2, turns: 2, repeated: 1 })),
    ).toEqual({
      ok: true,
      message: "Imported 2 conversations (2 turns). Skipped 1 repeated conversation.",
    });
    expect(
      summarizeFileImportOutcome(
        preview({ conversations: 2, turns: 2, duplicates: 2, repeated: 1 }),
      ),
    ).toEqual({
      ok: true,
      message:
        "Imported 2 conversations (2 turns). Skipped 2 conversations already in the dataset and 1 repeated conversation.",
    });
  });

  it("reports an import that added nothing", () => {
    expect(summarizeFileImportOutcome(preview({ duplicates: 2 }))).toEqual({
      ok: false,
      message: "Nothing new was imported.",
    });
  });
});
