import { apiRequest } from "@/config/api";

export interface RegistrationStatusResponse {
  registration_id?: string | null;
  is_new?: boolean;
}

export const getRegistrationStatus = async (): Promise<RegistrationStatusResponse> => {
  try {
    const response = await apiRequest<RegistrationStatusResponse>("GET", "public-registration/registration-id");
    return response ?? { registration_id: null, is_new: false };
  } catch (error) {
    return { registration_id: null, is_new: false };
  }
};
