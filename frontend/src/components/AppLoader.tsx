import { useLayoutEffect } from "react";
import { holdSplash } from "@/lib/bootSplash";

/**
 * Full-screen loading state. Keeps the animated logo splash from index.html on
 * screen while mounted (see lib/bootSplash.ts); what renders here is only the
 * blank surface underneath it.
 */
export function AppLoader() {
  useLayoutEffect(() => holdSplash(), []);
  return <div className="min-h-screen w-full bg-background" aria-busy="true" />;
}

export default AppLoader;
