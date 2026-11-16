import { Toaster } from "react-hot-toast";
import { RoutesProvider } from "./Routes";
import { PermissionProvider } from "@/context/PermissionContext";
import { FeatureFlagProvider } from "@/context/FeatureFlagContext";
import { ServerStatusProvider } from "@/context/ServerStatusContext";
import { ThemeProvider } from "@/context/ThemeProvider";
import { useEffect } from "react";
import { markAppMounted } from "@/lib/bootSplash";

export default function App() {
  // Runs after every loader below has registered, so the splash only lifts when nothing holds it.
  useEffect(() => markAppMounted(), []);

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
