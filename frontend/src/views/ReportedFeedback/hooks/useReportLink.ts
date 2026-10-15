import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import toast from "react-hot-toast";

import { useIssue } from "./useReportedFeedback";

const REPORT_LINK_PARAM = "feedback";

export const reportLinkUrl = (feedbackId: string) =>
  `${window.location.origin}/reported-feedback?${REPORT_LINK_PARAM}=${encodeURIComponent(feedbackId)}`;

/** Opens the report a shared link points at, once per link, unless another report is open */
export function useReportLink(
  open: (feedbackId: string) => void,
  canOpen: boolean,
) {
  const [searchParams, setSearchParams] = useSearchParams();
  const linkedId = searchParams.get(REPORT_LINK_PARAM)?.trim() || null;
  const linked = useIssue(linkedId);
  const [openedLinkId, setOpenedLinkId] = useState<string | null>(null);
  const pending = linkedId !== null && linkedId !== openedLinkId;

  if (pending && linked.data) {
    setOpenedLinkId(linkedId);
    if (canOpen) open(linkedId);
  }
  if (!linkedId && openedLinkId) setOpenedLinkId(null);

  const clearLink = useCallback(
    () =>
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.delete(REPORT_LINK_PARAM);
          return next;
        },
        { replace: true },
      ),
    [setSearchParams],
  );

  const failed =
    pending && (linked.isError || (linked.isSuccess && !linked.data));
  useEffect(() => {
    if (!failed) return;
    toast.error(
      "Couldn't open the report. It may not exist or you may not have access.",
    );
    clearLink();
  }, [failed, clearLink]);

  return {
    clear: () => {
      if (linkedId) clearLink();
    },
  };
}
