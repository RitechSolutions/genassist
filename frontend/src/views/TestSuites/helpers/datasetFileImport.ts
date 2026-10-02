import type {
  DatasetFileResult,
  ImportCasesFromFilesResult,
} from "@/interfaces/testSuite.interface";

/** Mirrors the API's cap, so the picker never builds a request it refuses. */
export const MAX_IMPORT_FILES = 20;

/** Served from public/, linked from the dialog's format guide. */
export const DATASET_SAMPLE_FILE = "/sample-files/dataset_sample.json";

// Grouped like the API's own messages, e.g. "5,001".
const plural = (count: number, word: string) =>
  `${count.toLocaleString("en-US")} ${word}${count === 1 ? "" : "s"}`;

const adds = (conversations: number, turns: number) =>
  `Adds ${plural(conversations, "conversation")} (${plural(turns, "turn")}).`;

/** Same name, size and modified time means the same file picked again. */
export const fileKey = (file: Pick<File, "name" | "size" | "lastModified">) =>
  `${file.name}:${file.size}:${file.lastModified}`;

/** Adds picked files to the selection, skipping repeats and stopping at the cap. */
export const addFiles = (
  current: File[],
  picked: File[],
  limit = MAX_IMPORT_FILES,
): { files: File[]; dropped: number } => {
  const seen = new Set(current.map(fileKey));
  const files = [...current];
  let dropped = 0;
  for (const file of picked) {
    const key = fileKey(file);
    if (seen.has(key)) continue;
    if (files.length >= limit) {
      dropped += 1;
      continue;
    }
    seen.add(key);
    files.push(file);
  }
  return { files, dropped };
};

export const describeDroppedFiles = (dropped: number, limit = MAX_IMPORT_FILES) =>
  `One import takes up to ${limit} files, so ${plural(dropped, "file")} ${
    dropped === 1 ? "was" : "were"
  } not added.`;

/** Where a file's repeated conversations first appeared, named when it is one other file. */
const repeatedWhere = (
  file: DatasetFileResult,
  position: number,
  files: DatasetFileResult[],
): string => {
  const others = file.repeated_from.filter((source) => source !== position);
  const repeatsItself = others.length < file.repeated_from.length;
  if (others.length === 0) return "earlier in this file";
  const only = others.length === 1 && !repeatsItself ? files[others[0]] : undefined;
  return only ? `in ${only.filename}` : "in other files you chose";
};

/** The line under a readable file in the preview. `position` is its place in `files`. */
export const describeReadableFile = (
  file: DatasetFileResult,
  position: number,
  files: DatasetFileResult[],
): string => {
  const where = file.repeated > 0 ? repeatedWhere(file, position, files) : "";
  if (file.conversations === 0) {
    if (file.repeated === 0) return "Everything in this file is already in this dataset.";
    if (file.duplicates === 0) return `Everything in this file also appears ${where}.`;
    return `Everything in this file is already in this dataset or ${where}.`;
  }
  const sentences = [adds(file.conversations, file.turns)];
  if (file.duplicates > 0) {
    sentences.push(
      file.duplicates === 1
        ? "1 conversation is already in this dataset and is skipped."
        : `${plural(file.duplicates, "conversation")} are already in this dataset and are skipped.`,
    );
  }
  if (file.repeated > 0) {
    sentences.push(
      file.repeated === 1
        ? `1 conversation also appears ${where} and is skipped.`
        : `${plural(file.repeated, "conversation")} also appear ${where} and are skipped.`,
    );
  }
  return sentences.join(" ");
};

/** The footer line for a preview, and whether Import can go ahead. */
export const summarizePreview = (
  preview: ImportCasesFromFilesResult,
): { text: string; canImport: boolean } => {
  if (preview.error) return { text: preview.error, canImport: false };
  if (preview.conversations === 0) {
    return { text: "Nothing new to import.", canImport: false };
  }
  const added = adds(preview.conversations, preview.turns);
  if (preview.failed_files === 0) return { text: added, canImport: true };
  const leftOut =
    preview.failed_files === 1
      ? "1 file is left out."
      : `${preview.failed_files} files are left out.`;
  return { text: `${added} ${leftOut}`, canImport: true };
};

/** The toast after an import. */
export const summarizeFileImportOutcome = (
  result: ImportCasesFromFilesResult,
): { ok: boolean; message: string } => {
  if (result.conversations === 0) {
    return { ok: false, message: "Nothing new was imported." };
  }
  const imported = `Imported ${plural(result.conversations, "conversation")} (${plural(
    result.turns,
    "turn",
  )}).`;
  const skipped = [
    result.duplicates > 0
      ? `${plural(result.duplicates, "conversation")} already in the dataset`
      : null,
    result.repeated > 0 ? plural(result.repeated, "repeated conversation") : null,
  ].filter(Boolean);
  if (skipped.length === 0) return { ok: true, message: imported };
  return { ok: true, message: `${imported} Skipped ${skipped.join(" and ")}.` };
};
