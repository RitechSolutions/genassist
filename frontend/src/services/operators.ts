import { apiRequest } from "@/config/api";
import { PaginatedResponse } from "@/interfaces/common.interface";
import { Operator, OperatorListItem } from "@/interfaces/operator.interface";

export const fetchOperators = async (): Promise<Operator[]> => {
  const response = await apiRequest<Operator[]>("get", "/operators/");
  return response && Array.isArray(response) ? response : [];
};

export const fetchOperatorsPaginated = async (
  page: number = 1,
  pageSize: number = 20,
  search?: string
): Promise<PaginatedResponse<OperatorListItem>> => {
  const limit = Math.min(Math.max(1, pageSize), 100);
  const skip = (Math.max(1, page) - 1) * limit;
  const params = new URLSearchParams({
    skip: String(skip),
    limit: String(limit),
  });
  const trimmed = search?.trim();
  if (trimmed) params.set("search", trimmed);

  const response = await apiRequest<PaginatedResponse<OperatorListItem>>(
    "get",
    `/operators/list?${params.toString()}`
  );
  // apiRequest returns null on 403; other failures still throw.
  return (
    response ?? { items: [], total: 0, page: 1, page_size: limit, total_pages: 0 }
  );
};

export const fetchOperatorById = async (
  operatorId: string
): Promise<Operator | null> => {
  const response = await apiRequest<Operator>("get", `/operators/${operatorId}`);
  return response ?? null;
};


export const createOperator = async (operatorData: Operator): Promise<Operator | null> => {
  const response = await apiRequest<Operator>("post", "/operators/", operatorData);
  return response ?? null;
};
