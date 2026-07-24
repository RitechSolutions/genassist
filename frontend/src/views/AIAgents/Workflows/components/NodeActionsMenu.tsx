import React from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuTrigger,
} from "@/components/dropdown-menu";
import {
  CircleHelp,
  Copy,
  CopyPlus,
  CornerDownLeft,
  Pencil,
  Power,
  PowerOff,
  Replace as ReplaceIcon,
  Settings,
  Space,
  Trash2,
} from "lucide-react";

export interface NodeActionsMenuProps {
  /** The 3-dots trigger button (rendered `asChild`). */
  trigger: React.ReactNode;
  deactivated?: boolean;
  /**
   * false for the special I/O nodes (Start / Output) — the actions that don't
   * apply there (Replace, Copy, Duplicate, Activate/Deactivate) stay in the menu
   * but are shown disabled, so every node's menu looks the same.
   */
  canModify?: boolean;
  onConfigure?: () => void;
  onRename: () => void;
  onReplace: () => void;
  onToggleActive: () => void;
  onCopy: () => void;
  onDuplicate: () => void;
  onHelp?: () => void;
  onDelete: () => void;
}

/**
 * Shared per-node actions menu opened from a 3-dots button. Uses the same
 * DropdownMenu primitive (and styling) as the canvas right-click context menu,
 * so both node views (compact + detailed) get an identical menu.
 *
 * Items are grouped with separators: Configuration | Rename·Replace·Activate |
 * Copy·Duplicate | Help | Delete.
 */
const NodeActionsMenu: React.FC<NodeActionsMenuProps> = ({
  trigger,
  deactivated,
  canModify = true,
  onConfigure,
  onRename,
  onReplace,
  onToggleActive,
  onCopy,
  onDuplicate,
  onHelp,
  onDelete,
}) => {
  // Radix closes the menu on select; opening a dialog in the SAME tick gets
  // dismissed by the menu's own closing focus/pointer handling (the dialog
  // flashes open then shut). Defer each action until after the menu has closed.
  const run = (fn?: () => void) => {
    if (!fn) return;
    setTimeout(fn, 0);
  };

  return (
    // Non-modal: a modal dropdown locks `pointer-events` on <body> and tears it
    // down on close, which races with the config dialog (a modal Radix Sheet)
    // opening — the Sheet reads it as an "interact outside" and slams shut. A
    // non-modal menu doesn't touch that layer, so dialogs opened from it stay open.
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild>{trigger}</DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        sideOffset={6}
        className="z-[2100] min-w-[256px]"
      >
        {/* Configuration */}
        <DropdownMenuItem
          disabled={!onConfigure}
          onSelect={() => run(onConfigure)}
        >
          <Settings className="mr-2 h-4 w-4" />
          Configuration
          <DropdownMenuShortcut>
            <Space className="h-3.5 w-3.5" />
          </DropdownMenuShortcut>
        </DropdownMenuItem>

        <DropdownMenuSeparator />

        {/* Rename / Replace / Activate-Deactivate */}
        <DropdownMenuItem onSelect={() => run(onRename)}>
          <Pencil className="mr-2 h-4 w-4" />
          Rename
          <DropdownMenuShortcut>
            <CornerDownLeft className="h-3.5 w-3.5" />
          </DropdownMenuShortcut>
        </DropdownMenuItem>
        <DropdownMenuItem disabled={!canModify} onSelect={() => run(onReplace)}>
          <ReplaceIcon className="mr-2 h-4 w-4" />
          Replace
          <DropdownMenuShortcut>R</DropdownMenuShortcut>
        </DropdownMenuItem>
        <DropdownMenuItem
          disabled={!canModify}
          onSelect={() => run(onToggleActive)}
        >
          {deactivated ? (
            <>
              <Power className="mr-2 h-4 w-4" />
              Activate
            </>
          ) : (
            <>
              <PowerOff className="mr-2 h-4 w-4" />
              Deactivate
            </>
          )}
          <DropdownMenuShortcut>D</DropdownMenuShortcut>
        </DropdownMenuItem>

        <DropdownMenuSeparator />

        {/* Copy / Duplicate */}
        <DropdownMenuItem disabled={!canModify} onSelect={() => run(onCopy)}>
          <Copy className="mr-2 h-4 w-4" />
          Copy
          <DropdownMenuShortcut>⌘C</DropdownMenuShortcut>
        </DropdownMenuItem>
        <DropdownMenuItem
          disabled={!canModify}
          onSelect={() => run(onDuplicate)}
        >
          <CopyPlus className="mr-2 h-4 w-4" />
          Duplicate
          <DropdownMenuShortcut>⌘D</DropdownMenuShortcut>
        </DropdownMenuItem>

        <DropdownMenuSeparator />

        {/* Help */}
        <DropdownMenuItem disabled={!onHelp} onSelect={() => run(onHelp)}>
          <CircleHelp className="mr-2 h-4 w-4" />
          Help
          <DropdownMenuShortcut>H</DropdownMenuShortcut>
        </DropdownMenuItem>

        <DropdownMenuSeparator />

        {/* Delete */}
        <DropdownMenuItem
          onSelect={() => run(onDelete)}
          className="text-red-600 focus:bg-red-50 focus:text-red-700 dark:text-red-400"
        >
          <Trash2 className="mr-2 h-4 w-4" />
          Delete
          <DropdownMenuShortcut>⌫</DropdownMenuShortcut>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export default NodeActionsMenu;
