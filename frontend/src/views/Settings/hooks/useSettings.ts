import { useState, useCallback } from "react";
import toast from "react-hot-toast";

export const useSettings = () => {
  const [toggleStates, setToggleStates] = useState<Record<string, boolean>>({
    "Email Notifications": true,
    "Desktop Notifications": false,
    "Daily Summary": true,
    "Two-Factor Authentication": false
  });

  const handleToggle = useCallback((label: string) => {
    setToggleStates(prev => ({
      ...prev,
      [label]: !prev[label]
    }));
  }, []);

  const saveSettings = useCallback(async () => {
    // Simulate API call
    return new Promise<void>((resolve) => {
      setTimeout(() => {
        toast.success("Settings saved successfully");
        resolve();
      }, 1000);
    });
  }, []);

  return {
    toggleStates,
    handleToggle,
    saveSettings
  };
}; 