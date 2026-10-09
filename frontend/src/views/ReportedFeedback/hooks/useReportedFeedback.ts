import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  EMPTY_SUMMARY,
  FeedbackFilters,
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

export const useReportedFeedback = (params: FetchReportedFeedbackParams) =>
  useQuery({
    queryKey: ["reported-feedback", "list", params],
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
    queryKey: ["reported-feedback", "summary", filters],
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
export const useIssuePatch = () => {
  const queryClient = useQueryClient();
  const patchRows = (feedbackId: string, fields: IssueFields) =>
    queryClient.setQueriesData<ReportedFeedbackResult>(
      { queryKey: ["reported-feedback", "list"] },
      (result) =>
        result && {
          ...result,
          items: applyIssuePatch(result.items, feedbackId, fields),
        },
    );

  return useMutation({
    mutationFn: (vars: { issue: ReportedFeedbackItem; patch: IssuePatch }) =>
      updateFeedbackIssue(vars.issue.feedback_id, vars.patch),
    onMutate: async ({ issue, patch }) => {
      const interrupted = queryClient.getQueryCache().findAll({
        queryKey: ["reported-feedback", "list"],
        fetchStatus: "fetching",
      });
      await queryClient.cancelQueries({
        queryKey: ["reported-feedback", "list"],
      });
      patchRows(issue.feedback_id, patch);
      return { rollback: pickPatchedFields(issue, patch), interrupted };
    },
    onError: (_err, { issue }, context) => {
      if (context) patchRows(issue.feedback_id, context.rollback);
    },
    onSuccess: (saved, { issue, patch }) => {
      patchRows(issue.feedback_id, pickPatchedFields(saved, patch));
      void queryClient.invalidateQueries({
        queryKey: ["reported-feedback", "summary"],
      });
    },
    onSettled: (_saved, _err, _vars, context) => {
      if (!context?.interrupted.length) return;
      void queryClient.refetchQueries({
        queryKey: ["reported-feedback", "list"],
        predicate: (query) => context.interrupted.includes(query),
      });
    },
  });
};
