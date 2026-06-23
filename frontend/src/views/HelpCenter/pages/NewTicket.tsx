import { Navigate } from "react-router-dom";

/** Legacy route — new issues use inline form on Help Center list. */
export default function NewTicketPage() {
  return <Navigate to="/help-center" replace state={{ openForm: true }} />;
}
