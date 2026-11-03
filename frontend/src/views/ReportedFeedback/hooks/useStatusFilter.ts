import { useLocation, useSearchParams } from "react-router-dom";

import { normalizeStatusKeys } from "../helpers/issueStatuses";

const STATUS_PARAM = "status";

export function useStatusFilter(): [string[], (keys: string[]) => void] {
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const value = normalizeStatusKeys(searchParams.getAll(STATUS_PARAM));
  const setValue = (keys: string[]) =>
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete(STATUS_PARAM);
        for (const key of keys) next.append(STATUS_PARAM, key);
        return next;
      },
      { replace: true, state: location.state },
    );
  return [value, setValue];
}
