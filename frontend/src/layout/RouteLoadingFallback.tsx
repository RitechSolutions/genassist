import { AppLoader } from "@/components/AppLoader";
import { Skeleton } from "@/components/skeleton";
import { useIsInAppShell } from "@/layout/AppShellContext";

/**
 * Inside the app shell: an in-layout skeleton, so the sidebar stays usable even
 * if the guard never settles. Outside it (app-level loads before the shell
 * exists): the full-screen animated logo splash.
 */
const RouteLoadingFallback = () => {
  const isInAppShell = useIsInAppShell();

  if (!isInAppShell) return <AppLoader />;

  return (
    <div className="flex justify-center items-center h-screen">
      <div className="flex flex-col space-y-3">
        <Skeleton className="h-[125px] w-[250px] rounded-xl" />
        <div className="space-y-2">
          <Skeleton className="h-4 w-[250px]" />
          <Skeleton className="h-4 w-[200px]" />
        </div>
      </div>
    </div>
  );
};

export default RouteLoadingFallback;
