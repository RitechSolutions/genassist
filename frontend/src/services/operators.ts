import { apiRequest } from "@/config/api";
import { Operator } from "@/interfaces/operator.interface";

export const fetchOperators = async (): Promise<Operator[]> => {
  const response = await apiRequest<Operator[]>("get", "/operators/");
  return response && Array.isArray(response) ? response : [];
};

export const fetchOperatorById = async (
  operatorId: string
): Promise<Operator | null> => {
  const response = await apiRequest<Operator>("get", `/operator/${operatorId}`);
  return response ?? null;
};


export const createOperator = async (operatorData: Operator): Promise<Operator | null> => {
  const response = await apiRequest<Operator>("post", "/operators/", operatorData);
  return response ?? null;
};