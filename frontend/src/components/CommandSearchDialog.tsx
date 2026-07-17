import * as DialogPrimitive from '@radix-ui/react-dialog';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { cn } from '@/helpers/utils';
import { Dialog, DialogOverlay, DialogPortal } from '@/components/dialog';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/command';
import type { BadgeTone, MenuItem, NavGroup } from '@/layout/app-sidebar';
import { useCommandSearch, type CommandResultGroup } from '@/components/commandSearch/useCommandSearch';

type CommandSearchDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Permission/feature-flag filtered nav groups (static "pages"). */
  groups: NavGroup[];
  /** Permission-filtered footer items (Help Center, Settings, …). */
  footer: MenuItem[];
};

// Mirrors the sidebar's NavBadge so palette rows carry the same NEW/BETA pills.
function ResultBadge({ label, tone = 'beta' }: { label: string; tone?: BadgeTone }) {
  return (
    <span
      className={cn(
        'shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold leading-none',
        tone === 'new' && 'bg-emerald-50 text-emerald-600',
        tone === 'beta' && 'bg-blue-50 text-blue-600',
        tone === 'count' && 'min-w-[18px] rounded-full bg-blue-600 px-1 text-center text-white'
      )}
    >
      {label}
    </span>
  );
}

// A single navigable result row inside the palette.
function ResultItem({
  value,
  title,
  context,
  icon: Icon,
  url,
  badge,
  badgeTone,
  onSelect,
}: {
  /** Unique cmdk identity — separate from `url` because list-nav rows share a URL. */
  value: string;
  title: string;
  context?: string;
  icon?: React.ElementType;
  url: string;
  badge?: string;
  badgeTone?: BadgeTone;
  onSelect: (url: string) => void;
}) {
  return (
    <CommandItem value={value} onSelect={() => onSelect(url)} className="gap-2.5">
      {Icon ? (
        <Icon className="h-4 w-4 shrink-0 text-zinc-500" strokeWidth={2.25} />
      ) : (
        <span className="h-4 w-4 shrink-0" />
      )}
      <span className="truncate text-zinc-700">{title}</span>
      {badge && <ResultBadge label={badge} tone={badgeTone} />}
      {context && <span className="ml-auto truncate pl-3 text-xs text-zinc-400">{context}</span>}
    </CommandItem>
  );
}

// A dynamic result group rendered like the sidebar: the page as a parent row
// (icon + name) with its matched values threaded below it on a connector line.
function ThreadGroup({
  group,
  onSelect,
}: {
  group: CommandResultGroup;
  onSelect: (url: string) => void;
}) {
  const Icon = group.icon;
  return (
    <div className="p-1">
      <div className="flex items-center gap-2.5 px-2.5 py-[7px] text-sm font-medium text-zinc-600">
        <Icon className="h-4 w-4 shrink-0 text-zinc-500" strokeWidth={2.25} />
        <span className="truncate">{group.page}</span>
      </div>
      <div className="relative py-0.5 pl-[30px]">
        <div className="absolute bottom-0 left-[18px] top-0 w-px bg-zinc-200" />
        {group.items.map((item) => (
          <CommandItem
            key={item.value}
            value={item.value}
            onSelect={() => onSelect(item.url)}
            className="text-zinc-600"
          >
            <span className="truncate">{item.title}</span>
          </CommandItem>
        ))}
      </div>
    </div>
  );
}

// Thread-shaped loading placeholder shown while a dynamic search is in flight.
function ThreadSkeleton() {
  return (
    <div className="p-1" aria-hidden>
      <div className="flex items-center gap-2.5 px-2.5 py-[7px]">
        <span className="h-4 w-4 shrink-0 animate-pulse rounded bg-zinc-200" />
        <span className="h-3.5 w-24 animate-pulse rounded bg-zinc-200" />
      </div>
      <div className="relative py-0.5 pl-[30px]">
        <div className="absolute bottom-0 left-[18px] top-0 w-px bg-zinc-100" />
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="px-2 py-2">
            <span className="block h-3.5 w-40 animate-pulse rounded bg-zinc-100" />
          </div>
        ))}
      </div>
    </div>
  );
}

// Client-side title filter for the static nav. A parent stays (with all its
// children) when its own title matches; otherwise only its matching children.
function filterNavGroups(groups: NavGroup[], q: string): NavGroup[] {
  if (!q) return groups;
  const matches = (text: string) => text.toLowerCase().includes(q);
  return groups
    .map((group) => {
      const items = group.items.reduce<MenuItem[]>((acc, item) => {
        const selfMatch = matches(item.title);
        if (item.children && item.children.length > 0) {
          const children = selfMatch ? item.children : item.children.filter((c) => matches(c.title));
          if (selfMatch || children.length > 0) acc.push({ ...item, children });
        } else if (selfMatch) {
          acc.push(item);
        }
        return acc;
      }, []);
      return { ...group, items };
    })
    .filter((group) => group.items.length > 0);
}

/**
 * Centered, backdrop-dimmed command palette. Searches both the static sidebar
 * nav (client-side) and dynamic backend entities (agents, conversations,
 * knowledge base, operators, …) via useCommandSearch. Opened with ⌘K / Ctrl+K.
 */
export function CommandSearchDialog({ open, onOpenChange, groups, footer }: CommandSearchDialogProps) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');

  // Reset the query each time the palette closes so it reopens fresh.
  useEffect(() => {
    if (!open) setQuery('');
  }, [open]);

  const go = (url: string) => {
    onOpenChange(false);
    if (url && url !== '#') navigate(url);
  };

  const q = query.trim().toLowerCase();
  const staticGroups = useMemo(() => {
    const base: NavGroup[] = footer.length ? [...groups, { label: 'Help & Settings', items: footer }] : groups;
    return filterNavGroups(base, q);
  }, [groups, footer, q]);
  const { groups: dynamicGroups, loading } = useCommandSearch(query, open);

  const hasResults = staticGroups.length > 0 || dynamicGroups.length > 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPortal>
        <DialogOverlay className="z-[1290] bg-black/40 backdrop-blur-sm" />
        <DialogPrimitive.Content
          className={cn(
            'fixed left-1/2 top-[14%] z-[1300] w-[92vw] max-w-2xl -translate-x-1/2',
            'overflow-hidden rounded-xl border bg-popover text-popover-foreground shadow-2xl',
            'duration-150 data-[state=open]:animate-in data-[state=closed]:animate-out',
            'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
            // Slide up from the bottom (like the Agent Studio workflow palette);
            // the *-left-1/2 pair keeps the -translate-x-1/2 centering steady.
            'data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-bottom-4',
            'data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-bottom-4'
          )}
        >
          <DialogPrimitive.Title className="sr-only">Search menu</DialogPrimitive.Title>
          <DialogPrimitive.Description className="sr-only">
            Search and jump to any page, agent, conversation, or setting.
          </DialogPrimitive.Description>

          <Command
            shouldFilter={false}
            className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-zinc-400 [&_[cmdk-input-wrapper]_svg]:h-4 [&_[cmdk-input-wrapper]_svg]:w-4 [&_[cmdk-input]]:h-12 [&_[cmdk-item]]:px-2 [&_[cmdk-item]]:py-2.5"
          >
            <CommandInput
              value={query}
              onValueChange={setQuery}
              placeholder="Search pages, agents, conversations…"
            />
            <CommandList className="max-h-[60vh] p-1">
              {!loading && !hasResults && (
                <CommandEmpty className="py-10 text-zinc-400">No results found.</CommandEmpty>
              )}

              {/* Static nav ("pages") */}
              {staticGroups.map((group) => (
                <CommandGroup key={group.label} heading={group.label}>
                  {group.items.flatMap((item) =>
                    item.children && item.children.length > 0
                      ? item.children.map((child) => (
                          <ResultItem
                            key={child.url}
                            value={child.url}
                            title={child.title}
                            context={item.title}
                            icon={item.icon}
                            url={child.url}
                            badge={child.badge}
                            badgeTone={child.badgeTone}
                            onSelect={go}
                          />
                        ))
                      : [
                          <ResultItem
                            key={item.url}
                            value={item.url}
                            title={item.title}
                            context={group.label}
                            icon={item.icon}
                            url={item.url}
                            badge={item.badge}
                            badgeTone={item.badgeTone}
                            onSelect={go}
                          />,
                        ]
                  )}
                </CommandGroup>
              ))}

              {/* Dynamic backend entities — page parent + threaded values, like the sidebar */}
              {dynamicGroups.map((group) => (
                <ThreadGroup key={group.key} group={group} onSelect={go} />
              ))}

              {/* Skeleton while the first results load; a subtle note while more arrive */}
              {loading && dynamicGroups.length === 0 && <ThreadSkeleton />}
              {loading && dynamicGroups.length > 0 && (
                <div className="px-3 py-2 text-center text-xs text-zinc-400">Searching…</div>
              )}
            </CommandList>
          </Command>
        </DialogPrimitive.Content>
      </DialogPortal>
    </Dialog>
  );
}
