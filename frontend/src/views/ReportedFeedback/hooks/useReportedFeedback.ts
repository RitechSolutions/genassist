import {
  keepPreviousData,
  mutationOptions,
  QueryClient,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  addIssueNote,
  EMPTY_SUMMARY,
  FeedbackFilters,
  fetchIssueNotes,
  fetchReportedFeedback,
  fetchReportedFeedbackSummary,
  FetchReportedFeedbackParams,
  IssuePatch,
  ReportedFeedbackItem,
  ReportedFeedbackResult,
  updateFeedbackIssue,
} from "@/services/reportedFeedback";
import { categoryTotals } from "../helpers/issueStatuses";
import {
  applyIssuePatch,
  IssueFields,
  pickPatchedFields,
} from "../helpers/issuePatch";
import { useIssueStatuses } from "./useIssueStatuses";

const LIST_QUERY_KEY = ["reported-feedback", "list"] as const;
const SUMMARY_QUERY_KEY = ["reported-feedback", "summary"] as const;
const notesQueryKey = (feedbackId: string) =>
  ["reported-feedback", "notes", feedbackId] as const;

export const useReportedFeedback = (params: FetchReportedFeedbackParams) =>
  useQuery({
    queryKey: [...LIST_QUERY_KEY, params],
    queryFn: () => fetchReportedFeedback(params),
    placeholderData: keepPreviousData,
    // Refetch on page or filter changes only, so an edited row and the open dialog stay put
    staleTime: 0,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });

/** Total and per-category counts under the given filters */
export const useFeedbackSummary = (filters: FeedbackFilters) => {
  const statuses = useIssueStatuses();
  const summary = useQuery({
    queryKey: [...SUMMARY_QUERY_KEY, filters],
    queryFn: () => fetchReportedFeedbackSummary(filters),
    placeholderData: keepPreviousData,
  });
  const data = summary.data ?? EMPTY_SUMMARY;
  return {
    total: data.total,
    totals: categoryTotals(data, statuses.data ?? []),
    isLoading: statuses.isLoading || summary.isLoading,
    isError: statuses.isError || summary.isError,
  };
};

/** Saves a partial issue update, shown at once in every cached list page */
export const issuePatchMutation = (queryClient: QueryClient) => {
  const patchRows = (feedbackId: string, fields: IssueFields) =>
    queryClient.setQueriesData<ReportedFeedbackResult>(
      { queryKey: LIST_QUERY_KEY },
      (result) =>
        result && {
          ...result,
          items: applyIssuePatch(result.items, feedbackId, fields),
        },
    );

  return mutationOptions({
    mutationFn: (vars: { issue: ReportedFeedbackItem; patch: IssuePatch }) =>
      updateFeedbackIssue(vars.issue.feedback_id, vars.patch),
    onMutate: async ({ issue, patch }) => {
      const interrupted = queryClient.getQueryCache().findAll({
        queryKey: LIST_QUERY_KEY,
        fetchStatus: "fetching",
      });
      await queryClient.cancelQueries({ queryKey: LIST_QUERY_KEY });
      patchRows(issue.feedback_id, patch);
      return { rollback: pickPatchedFields(issue, patch), interrupted };
    },
    onError: (_err, { issue }, context) => {
      if (context) patchRows(issue.feedback_id, context.rollback);
    },
    onSuccess: (saved, { issue, patch }) => {
      patchRows(issue.feedback_id, pickPatchedFields(saved, patch));
      if ("status" in patch) {
        void queryClient.invalidateQueries({ queryKey: SUMMARY_QUERY_KEY });
      }
    },
    onSettled: (_saved, _err, _vars, context) => {
      if (!context?.interrupted.length) return;
      void queryClient.refetchQueries({
        queryKey: LIST_QUERY_KEY,
        predicate: (query) => context.interrupted.includes(query),
      });
    },
  });
};

export const useIssuePatch = () => {
  const queryClient = useQueryClient();
  return useMutation(issuePatchMutation(queryClient));
};

export const useIssueNotes = (feedbackId: string) =>
  useQuery({
    queryKey: notesQueryKey(feedbackId),
    queryFn: () => fetchIssueNotes(feedbackId),
  });

export const useAddIssueNote = (feedbackId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: string) => addIssueNote(feedbackId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: notesQueryKey(feedbackId),
      });
    },
  });
};
