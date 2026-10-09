import { apiRequest } from "@/config/api";

export type IssueCategory = "todo" | "in_progress" | "done";

export interface IssueStatus {
  id: string;
  key: string;
  label: string;
  category: IssueCategory;
  position: number;
  color: string;
  is_active: number;
}

const API_ENDPOINT = "issue-statuses";

export type IssueStatusCreate = Pick<
  IssueStatus,
  "key" | "label" | "category" | "color"
>;

/** Fields an admin can change on a status; the key is immutable */
export type IssueStatusEdit = Partial<
  Pick<IssueStatus, "label" | "category" | "color" | "is_active">
>;

const FORBIDDEN = "You don't have permission to manage issue statuses";

export const fetchIssueStatuses = async (): Promise<IssueStatus[]> => {
  const response = await apiRequest<IssueStatus[]>("GET", API_ENDPOINT);
  return Array.isArray(response) ? response : [];
};

export const createIssueStatus = async (
  status: IssueStatusCreate,
): Promise<IssueStatus> => {
  const created = await apiRequest<IssueStatus>("POST", API_ENDPOINT, status);
  if (!created) throw new Error(FORBIDDEN);
  return created;
};

export const updateIssueStatus = async (
  id: string,
  patch: IssueStatusEdit,
): Promise<IssueStatus> => {
  const updated = await apiRequest<IssueStatus>(
    "PATCH",
    `${API_ENDPOINT}/${id}`,
    patch,
  );
  if (!updated) throw new Error(FORBIDDEN);
  return updated;
};

/** `keys` must list every active status exactly once */
export const reorderIssueStatuses = async (
  keys: string[],
): Promise<IssueStatus[]> => {
  const statuses = await apiRequest<IssueStatus[]>(
    "PUT",
    `${API_ENDPOINT}/order`,
    { keys },
  );
  if (!statuses) throw new Error(FORBIDDEN);
  return statuses;
};
