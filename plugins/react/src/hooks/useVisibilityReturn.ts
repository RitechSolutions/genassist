import { useEffect, useRef } from "react";

/** Calls `onReturn` each time the page becomes visible again, e.g. the visitor returns to the tab. */
export const useVisibilityReturn = (onReturn: () => void): void => {
  const onReturnRef = useRef(onReturn);
  onReturnRef.current = onReturn;

  useEffect(() => {
    if (typeof document === "undefined") return;
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") onReturnRef.current();
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => document.removeEventListener("visibilitychange", handleVisibilityChange);
  }, []);
};
