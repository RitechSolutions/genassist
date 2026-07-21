import { Toaster } from "react-hot-toast";
import { RoutesProvider } from "./Routes";
import { PermissionProvider } from "@/context/PermissionContext";
import { FeatureFlagProvider } from "@/context/FeatureFlagContext";
import { ServerStatusProvider } from "@/context/ServerStatusContext";
import { ThemeProvider } from "@/context/ThemeProvider";

export default function App() {
  return (
    <ThemeProvider>
      <ServerStatusProvider>
        <Toaster position="top-center" reverseOrder={false} />
        <PermissionProvider>
          <FeatureFlagProvider>
            <RoutesProvider />
          </FeatureFlagProvider>
        </PermissionProvider>
      </ServerStatusProvider>
    </ThemeProvider>
  );
}
