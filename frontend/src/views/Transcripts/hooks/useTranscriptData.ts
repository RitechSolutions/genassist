import { useState, useEffect, useCallback } from "react";
import { fetchTranscript, fetchTranscripts } from "@/services/transcripts";
import {
  BackendTranscript,
  Transcript,
} from "@/interfaces/transcript.interface";
import {
  processApiResponse,
  transformTranscript,
} from "../helpers/transformers";
import { usePermissions } from "@/context/PermissionContext";

interface UseTranscriptDataOptions {
  id?: string;
  limit?: number;
  skip?: number;
  sentiment?: string;
  hostility_neutral_max?: number;
  hostility_positive_max?: number;
  include_feedback?: boolean;
  sortNewestFirst?: boolean;
  conversation_status?: string[];
  order_by?: string;
  sort_direction?: string;
  agent_id?: string;
  scoreFilters?: Record<string, number | undefined>;
  from_date?: string;
  to_date?: string;
  exclude_empty?: boolean;
  custom_attributes?: Record<string, string>;
  search?: string;
}

export const useTranscriptData = (options: UseTranscriptDataOptions = {}) => {
  const { id, limit, skip, sentiment, hostility_neutral_max, hostility_positive_max, include_feedback, sortNewestFirst = true, conversation_status, order_by, sort_direction, agent_id, scoreFilters, from_date, to_date, exclude_empty, custom_attributes, search } = options;
  // Stabilize score filters for dependency tracking
  const scoreFiltersKey = scoreFilters ? JSON.stringify(scoreFilters) : "";
  const customAttrsKey = custom_attributes ? JSON.stringify(custom_attributes) : "";
  // Stabilize array reference for useCallback dependency
  const statusKey = conversation_status?.join(",") ?? "";

  const [data, setData] = useState<Transcript | Transcript[]>(id ? null : []);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);
  const [total, setTotal] = useState<number>(0);

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
        setTotal(transformedData ? 1 : 0);
        setError(null);
      } catch (err) {
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
        const params = {
          limit, skip, sentiment, hostility_neutral_max, hostility_positive_max,
          include_feedback, conversation_status, order_by, sort_direction,
          agent_id, scoreFilters, from_date, to_date, exclude_empty, custom_attributes, search,
        };

        const { items: backendData, total: backendTotal } = await fetchTranscripts(params);

        if (!backendData || !Array.isArray(backendData)) {
          throw new Error("Invalid backend data format");
        }

        const recordingsArray = processApiResponse(backendData);
        const transformedData = recordingsArray
          .map((recording) => {
            try {
              return transformTranscript(recording as BackendTranscript);
            } catch (err) {
              return null;
            }
          })
          .filter(Boolean) as Transcript[];

        const finalData = order_by
          ? transformedData
          : sortNewestFirst
            ? [...transformedData].sort(
                (a, b) =>
                  new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
              )
            : [...transformedData];

        const validData = finalData.map((transcript) => ({
          ...transcript,
          metadata: {
            ...(transcript.metadata || {}),
            customer_speaker:
              transcript.metadata?.customer_speaker ?? "Customer",
            duration: transcript.duration || 0,
            title: transcript.id || "Unknown",
            topic: transcript.metadata?.topic || " - Unknown",
            isCall: Boolean(transcript?.recording_id) || Boolean(transcript?.metadata?.isCall),
          },
          status: transcript.status || "unknown",
        }));

        setData(validData);
        setTotal(typeof backendTotal === "number" ? backendTotal : validData.length);
        setError(null);
      } catch (err) {
        setError(
          err instanceof Error ? err : new Error("Failed to fetch transcripts")
        );
        setData([]);
        setTotal(0);
      } finally {
        setLoading(false);
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, limit, skip, sentiment, hostility_neutral_max, hostility_positive_max, include_feedback, sortNewestFirst, statusKey, order_by, sort_direction, agent_id, scoreFiltersKey, from_date, to_date, exclude_empty, customAttrsKey, search]);

  const permissions = usePermissions();

  useEffect(() => {
    if (!permissions.includes("*") && !permissions.includes("read:conversation")) {
      return;
    }
    fetchAndTransformTranscripts();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchAndTransformTranscripts]);

  return {
    data,
    total,
    loading,
    error,
    refetch: fetchAndTransformTranscripts,
  };
};
