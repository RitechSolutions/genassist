import { apiRequest } from "@/config/api";
import { Transcript } from "@/interfaces/transcript.interface";


export const fetchRecordings = async (): Promise<Transcript[] | null> => {
  const response = await apiRequest<{ recordings: Transcript[] }>(
    "get",
    "/audio/recordings"
  );
  return response?.recordings ?? null;
};
