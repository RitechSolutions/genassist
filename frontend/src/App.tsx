import { Toaster } from "react-hot-toast";
import { RoutesProvider } from "./Routes";
import { PermissionProvider } from "@/context/PermissionContext";
import { FeatureFlagProvider } from "@/context/FeatureFlagContext";
import { ServerStatusProvider } from "@/context/ServerStatusContext";

export default function App() {
  return (
    <ServerStatusProvider>
      <Toaster position="top-right" reverseOrder={false} />
      <PermissionProvider>
        <FeatureFlagProvider>
          <RoutesProvider />
        </FeatureFlagProvider>
      </PermissionProvider>
    </ServerStatusProvider>
  );
}
