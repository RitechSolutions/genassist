import { Toaster } from "react-hot-toast";
import { RoutesProvider } from "./Routes";
import { PermissionProvider } from "@/context/PermissionContext";
import { FeatureFlagProvider } from "@/context/FeatureFlagContext";

export default function App() {
  return (
    <>
      <PermissionProvider>
        <FeatureFlagProvider>
          <Toaster position="top-right" reverseOrder={false} />
          <RoutesProvider />
        </FeatureFlagProvider>
      </PermissionProvider>
    </>
  );
}
