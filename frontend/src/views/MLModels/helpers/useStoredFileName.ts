import { useQuery, useQueryClient } from "@tanstack/react-query";

import { FileRecord, getFileManagerFile } from "@/services/fileManager";

const recordName = (record: FileRecord | null | undefined) =>
  record?.original_filename || record?.name || null;

/**
 * The name and size of a model's attached file, read from its File Manager
 * record. The model only stores the file's id, so anything that names the file
 * has to ask for the record. Falls back to `<model name>.pkl` while loading or
 * when the record can't be read (for example 403 without File Manager access).
 */
export function useStoredFileName(
  fileId: string | null | undefined,
  modelName: string | null | undefined
): { name: string; size: number | null; resolveName: () => Promise<string> } {
  const queryClient = useQueryClient();
  const fallback = `${modelName || "model"}.pkl`;
  // Keyed by id, so a replaced file never shows the previous file's name.
  const query = {
    queryKey: ["file-manager-file", fileId],
    queryFn: () => getFileManagerFile(fileId as string),
    retry: false,
  };
  const { data: record } = useQuery({ ...query, enabled: !!fileId });

  return {
    name: recordName(record) || fallback,
    size: record?.size ?? null,
    // For downloads: waits for the record when a click comes before it has loaded.
    resolveName: async () => {
      if (!fileId) return fallback;
      const fetched = await queryClient.fetchQuery(query).catch(() => null);
      return recordName(fetched) || fallback;
    },
  };
}
