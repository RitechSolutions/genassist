export interface ConnectionStatus {
  status: "Untested" | "Connected" | "Error";
  last_tested_at: string | null;
  message: string | null;
}
