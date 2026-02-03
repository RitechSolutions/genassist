import { createContext, useContext } from "react";

export type RegistrationStatus = "loading" | "new" | "existing";

interface RoutesContextType {
    registrationStatus: RegistrationStatus;
    skipOnboarding: boolean;
}

export const RoutesContext = createContext<RoutesContextType>({
    registrationStatus: 'loading' as RegistrationStatus,
    skipOnboarding: false,
} as RoutesContextType);

export const useRoutesContext = () => {
  const context = useContext(RoutesContext);
  if (!context) {
    throw new Error("useRoutesContext must be used within a RoutesContextProvider");
  }
  return context;
};