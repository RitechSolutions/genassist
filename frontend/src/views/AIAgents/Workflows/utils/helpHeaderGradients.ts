// Node help-dialog header gradient per category. Light mode fades the category
// tint down to white; dark mode mirrors that but fades the category's saturated
// color (matching the node colors) into the dark body (transparent), instead of
// staying a washed-out light band.
export const helpHeaderGradientByCategory: Record<string, string> = {
  io: "bg-gradient-to-b from-brand-100/80 via-brand-50/50 to-white dark:from-brand-600/30 dark:via-brand-600/10 dark:to-transparent",
  ai: "bg-gradient-to-b from-pink-100/80 via-pink-50/50 to-white dark:from-pink-600/30 dark:via-pink-600/10 dark:to-transparent",
  routing: "bg-gradient-to-b from-orange-100/80 via-orange-50/50 to-white dark:from-orange-500/30 dark:via-orange-500/10 dark:to-transparent",
  integrations: "bg-gradient-to-b from-green-100/80 via-green-50/50 to-white dark:from-green-600/30 dark:via-green-600/10 dark:to-transparent",
  formatting: "bg-gradient-to-b from-purple-100/80 via-purple-50/50 to-white dark:from-purple-600/30 dark:via-purple-600/10 dark:to-transparent",
  tools: "bg-gradient-to-b from-sky-100/80 via-sky-50/50 to-white dark:from-sky-600/30 dark:via-sky-600/10 dark:to-transparent",
  training: "bg-gradient-to-b from-rose-100/80 via-rose-50/50 to-white dark:from-rose-600/30 dark:via-rose-600/10 dark:to-transparent",
  utils: "bg-gradient-to-b from-slate-100/80 via-slate-50/50 to-white dark:from-slate-600/30 dark:via-slate-600/10 dark:to-transparent",
  audio: "bg-gradient-to-b from-teal-100/80 via-teal-50/50 to-white dark:from-teal-600/30 dark:via-teal-600/10 dark:to-transparent",
};

export const defaultHelpHeaderGradient =
  "bg-gradient-to-b from-slate-100/70 via-slate-50/40 to-white dark:from-slate-600/30 dark:via-slate-600/10 dark:to-transparent";
