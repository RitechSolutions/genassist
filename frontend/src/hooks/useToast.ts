import * as React from "react";
import reactHotToast from "react-hot-toast";

/**
 * Thin adapter that exposes the shadcn `useToast` / `toast({ title, description, variant })`
 * API on top of `react-hot-toast` — the single Toaster actually mounted in `App.tsx`.
 *
 * Historically this hook fed a Radix `<Toaster>` that was never rendered, so every
 * `toast(...)` call here produced no visible notification. Routing through
 * react-hot-toast fixes that without touching the ~14 existing call sites.
 */

type ToastVariant = "default" | "destructive" | "success" | null | undefined;

export interface ToastOptions {
  title?: React.ReactNode;
  description?: React.ReactNode;
  variant?: ToastVariant;
  duration?: number;
}

function renderMessage(
  title?: React.ReactNode,
  description?: React.ReactNode
): React.ReactNode {
  if (title && description) {
    return React.createElement(
      "div",
      null,
      React.createElement("div", { style: { fontWeight: 600 } }, title),
      React.createElement("div", null, description)
    );
  }
  return (description ?? title) as React.ReactNode;
}

function toast({ title, description, variant, duration }: ToastOptions) {
  const message = renderMessage(title, description);
  const options = duration ? { duration } : undefined;

  let id: string;
  if (variant === "destructive") {
    id = reactHotToast.error(message, options);
  } else if (variant === "success") {
    id = reactHotToast.success(message, options);
  } else {
    id = reactHotToast(message, options);
  }

  return {
    id,
    dismiss: () => reactHotToast.dismiss(id),
    update: (next: ToastOptions) => {
      reactHotToast.dismiss(id);
      return toast(next);
    },
  };
}

function useToast() {
  return {
    toast,
    dismiss: (toastId?: string) => reactHotToast.dismiss(toastId),
  };
}

export { useToast, toast };
