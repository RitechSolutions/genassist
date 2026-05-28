import { Navigate } from "react-router-dom";

/** Legacy route — triage is opened from Help Center list. */
export default function TriagePage() {
  return <Navigate to="/help-center" replace state={{ openTriage: true }} />;
}
