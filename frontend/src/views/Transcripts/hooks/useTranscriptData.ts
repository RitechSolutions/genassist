import { useState, useEffect, useCallback } from "react";
import { fetchTranscript, fetchTranscripts } from "@/services/transcripts";
import {
  BackendTranscript,
  Transcript,
  TranscriptEntry,
} from "@/interfaces/transcript.interface";
import {
  processApiResponse,
  transformTranscript,
} from "../helpers/transformers";
import { usePermissions } from "@/context/PermissionContext";

interface UseTranscriptDataOptions {
  id?: string;
  limit?: number;
  sortNewestFirst?: boolean;
}

export const useTranscriptData = (options: UseTranscriptDataOptions = {}) => {
  const { id, limit, sortNewestFirst = true } = options;

  const [data, setData] = useState<Transcript | Transcript[]>(id ? null : []);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchAndTransformTranscripts = useCallback(async () => {
    if (id) {
      try {
        setLoading(true);
        const backendData = await fetchTranscript(id);
        if (!backendData) {
          throw new Error(`Transcript with ID ${id} not found`);
        }

        const transformedData = transformTranscript(backendData);

        if (!transformedData || !transformedData.metadata) {
          throw new Error(`Failed to transform transcript ${id}`);
        }

        setData(transformedData);
        setError(null);
      } catch (err) {
        console.error(`Error fetching transcript ${id}:`, err);
        setError(
          err instanceof Error
            ? err
            : new Error(`Failed to fetch transcript ${id}`)
        );
        setData(null);
      } finally {
        setLoading(false);
      }
    } else {
      try {
        setLoading(true);
        const backendData = await fetchTranscripts();

        if (!backendData || !Array.isArray(backendData)) {
          console.error("Invalid backend data format:", backendData);
          throw new Error("Invalid backend data format");
        }

        const recordingsArray = processApiResponse(backendData);
        const transformedData = recordingsArray
          .map((recording) => {
            try {
              return transformTranscript(recording as BackendTranscript);
            } catch (err) {
              console.error("Error transforming recording:", err);
              return null;
            }
          })
          .filter(Boolean) as Transcript[];

        let finalData = [...transformedData];

        if (sortNewestFirst) {
          finalData.sort(
            (a, b) =>
              new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
          );
        }

        if (limit && limit > 0) {
          finalData = finalData.slice(0, limit);
        }

        const validData = finalData.map((transcript) => ({
          ...transcript,
          metadata: {
            ...(transcript.metadata || {}),
            customer_speaker:
              transcript.metadata?.customer_speaker ?? "Customer",
            duration: typeof transcript.duration === 'number' 
              ? `${Math.floor(transcript.duration / 60)}:${String(Math.floor(transcript.duration % 60)).padStart(2, '0')}`
              : transcript.duration || "0:00",
            title: transcript.id || "Unknown",
            topic: transcript.metadata?.topic || " - Unknown",
          },
          status: transcript.status || "unknown",
        }));

        setData(validData);
        setError(null);
      } catch (err) {
        console.error("Error fetching transcripts:", err);
        setError(
          err instanceof Error ? err : new Error("Failed to fetch transcripts")
        );
        setData([]);
      } finally {
        setLoading(false);
      }
    }
  }, [id, limit, sortNewestFirst]);

  const permissions = usePermissions();

  useEffect(() => {
    if (!permissions.includes("*") && !permissions.includes("read:conversation")) {
      console.log("You don't have transcript permission");
      return;
    }
    fetchAndTransformTranscripts();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchAndTransformTranscripts]);

  return {
    data,
    loading,
    error,
    refetch: fetchAndTransformTranscripts,
  };
};
