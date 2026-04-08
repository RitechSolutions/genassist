import { useState, useCallback } from "react";

export function usePersistedState(key: string, defaultValue: boolean) {
  const [value, setValue] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem(key);
      return saved !== null ? JSON.parse(saved) : defaultValue;
    } catch {
      return defaultValue;
    }
  });

  const toggle = useCallback(() => {
    setValue((prev) => {
      const next = !prev;
      localStorage.setItem(key, JSON.stringify(next));
      return next;
    });
  }, [key]);

  const setAndPersist = useCallback(
    (next: boolean) => {
      setValue(next);
      localStorage.setItem(key, JSON.stringify(next));
    },
    [key]
  );

  return [value, toggle, setAndPersist] as const;
}
