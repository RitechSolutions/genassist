import React, { useState } from "react";
import { Keyboard } from "lucide-react";

interface ShortcutItem {
  label: string;
  keys: string[];
}

// Show ⌘ on macOS, Ctrl elsewhere.
const isMac =
  typeof navigator !== "undefined" &&
  /mac|iphone|ipad|ipod/i.test(navigator.platform || navigator.userAgent);
const MOD = isMac ? "⌘" : "Ctrl";

const SHORTCUTS: ShortcutItem[] = [
  { label: "Search nodes on canvas", keys: [MOD, "K"] },
  { label: "Commands & add a node", keys: ["/"] },
  { label: "Ask AI to edit workflow", keys: ["/agent"] },
  { label: "Toggle Available Nodes", keys: [MOD, "I"] },
  { label: "Auto-arrange nodes", keys: [MOD, "M"] },
];

/** A single keycap chip. */
const Kbd: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <kbd className="inline-flex h-6 min-w-[1.5rem] items-center justify-center rounded-md border border-border bg-muted px-1.5 text-xs font-medium text-muted-foreground shadow-sm">
    {children}
  </kbd>
);

/**
 * A circular keyboard-icon button that sits on top of the bottom-left zoom
 * controls and reveals a popover of keyboard shortcuts (to the side) on hover
 * or click.
 */
const ShortcutsHelp: React.FC = () => {
  const [open, setOpen] = useState(false);

  return (
    <div
      className="relative"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="flex h-9 w-9 items-center justify-center rounded-full border border-border bg-card text-muted-foreground shadow-md transition-colors hover:bg-muted"
        aria-label="Keyboard shortcuts"
        aria-expanded={open}
      >
        <Keyboard className="h-4 w-4" />
      </button>

      {open && (
        <div className="absolute bottom-0 left-full z-50 ml-2 w-72 rounded-xl border border-border bg-card p-2 shadow-xl">
          <div className="px-2 pb-1.5 pt-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Keyboard shortcuts
          </div>
          {SHORTCUTS.map((shortcut) => (
            <div
              key={shortcut.label}
              className="flex items-center justify-between gap-3 rounded-lg px-2 py-1.5 hover:bg-muted"
            >
              <span className="text-sm text-muted-foreground">{shortcut.label}</span>
              <span className="flex shrink-0 items-center gap-1">
                {shortcut.keys.map((key) => (
                  <Kbd key={key}>{key}</Kbd>
                ))}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ShortcutsHelp;
