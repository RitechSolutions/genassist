import React, { useRef, useState } from "react";
import { defaultFilter } from "cmdk";
import { AlertCircle, Check, CheckCircle2, ChevronDown } from "lucide-react";
import { Button } from "@/components/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/command";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/popover";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/RadixTooltip";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { cn } from "@/helpers/utils";
import {
  MissingReference,
  REFERENCE_KIND_NOUNS,
  ReferenceKind,
  ReferencePlace,
  ReferenceReplacement,
  ReferenceTarget,
  acceptedTargets,
} from "../utils/workflowReferences";

const KEEP = "__keep__";
const NONE_AVAILABLE = "None in this environment";

// Matches SelectTrigger, so both pickers look the same
const TRIGGER_CLASS =
  "flex h-10 w-64 shrink-0 items-center justify-between rounded-full border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50";

const referenceKey = (reference: MissingReference) =>
  `${reference.kind}:${reference.multiple ? "list:" : ""}${reference.ids.join(",")}`;
const placeKey = (place: ReferencePlace) => `${place.nodeId}:${place.field.key}`;

interface PickerProps {
  options: ReferenceTarget[];
  value: string[];
  onChange: (value: string[]) => void;
  label: string;
}

const TargetSelect: React.FC<PickerProps> = ({ options, value, onChange, label }) => (
  <Select
    value={value[0] ?? ""}
    onValueChange={(id) => onChange(id === KEEP ? [] : [id])}
    disabled={options.length === 0}
  >
    <SelectTrigger aria-label={label} className="w-64 shrink-0 data-[placeholder]:text-muted-foreground">
      <SelectValue placeholder={options.length ? "Choose a replacement" : NONE_AVAILABLE} />
    </SelectTrigger>
    <SelectContent>
      {value.length > 0 && <SelectItem value={KEEP}>None</SelectItem>}
      {options.map((target) => (
        <SelectItem key={target.id} value={target.id}>
          {target.label}
        </SelectItem>
      ))}
    </SelectContent>
  </Select>
);

const TargetMultiSelect: React.FC<PickerProps> = ({ options, value, onChange, label }) => {
  const [open, setOpen] = useState(false);
  const picked = options.filter((target) => value.includes(target.id));
  const summary =
    picked.length > 1 ? `${picked[0].label} +${picked.length - 1}` : picked[0]?.label;
  const toggle = (id: string) =>
    onChange(value.includes(id) ? value.filter((pickedId) => pickedId !== id) : [...value, id]);

  if (options.length === 0) {
    return (
      <button type="button" disabled aria-label={label} className={cn(TRIGGER_CLASS, "text-muted-foreground")}>
        {NONE_AVAILABLE}
      </button>
    );
  }

  return (
    // Modal, so the wheel scrolls its list inside the dialog's scroll lock.
    <Popover modal open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          role="combobox"
          aria-expanded={open}
          aria-label={label}
          title={picked.map((target) => target.label).join(", ") || undefined}
          className={TRIGGER_CLASS}
        >
          <span className={cn("truncate", !summary && "text-muted-foreground")}>
            {summary ?? "Choose replacements"}
          </span>
          <ChevronDown className="ml-2 h-4 w-4 shrink-0 opacity-50" aria-hidden="true" />
        </button>
      </PopoverTrigger>
      {/* Above the dialog, as the selects are. */}
      <PopoverContent className="z-[1400] w-[--radix-popover-trigger-width] p-0" align="end">
        {/* Match labels only, since the values are ids. */}
        <Command
          filter={(_value, search, keywords) => defaultFilter(keywords?.join(" ") ?? "", search)}
        >
          <CommandInput placeholder="Search" />
          <CommandList>
            <CommandEmpty>No matches</CommandEmpty>
            <CommandGroup>
              {value.length > 0 && (
                <CommandItem value={KEEP} keywords={["None"]} onSelect={() => onChange([])}>
                  <span className="pl-6">None</span>
                </CommandItem>
              )}
              {options.map((target) => (
                <CommandItem
                  key={target.id}
                  value={target.id}
                  keywords={[target.label]}
                  onSelect={() => toggle(target.id)}
                >
                  <Check
                    className={cn(
                      "mr-2 h-4 w-4 shrink-0",
                      value.includes(target.id) ? "opacity-100" : "opacity-0"
                    )}
                    aria-hidden="true"
                  />
                  <span className="truncate">{target.label}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
};

const StatusIcon: React.FC<{ done: boolean }> = ({ done }) =>
  done ? (
    <CheckCircle2 className="h-4 w-4 shrink-0 text-green-600 dark:text-green-400" aria-hidden="true" />
  ) : (
    <AlertCircle className="h-4 w-4 shrink-0 text-amber-500" aria-hidden="true" />
  );

const LinkButton: React.FC<{ onClick: () => void; children: React.ReactNode }> = ({
  onClick,
  children,
}) => (
  <button type="button" onClick={onClick} className="font-medium text-primary hover:underline">
    {children}
  </button>
);

const countLabel = (count: number, noun: string) => `${count} ${noun}${count === 1 ? "" : "s"}`;

const sectionTitle = (kind: ReferenceKind) => {
  const noun = REFERENCE_KIND_NOUNS[kind];
  return `${noun[0].toUpperCase()}${noun.slice(1)}s`;
};

// The section already names the kind, so field labels only show when one says more.
const fieldLabels = (reference: MissingReference): string[] => {
  const noun = REFERENCE_KIND_NOUNS[reference.kind].toLowerCase();
  const labels = [...new Set(reference.places.map((place) => place.field.label))];
  return labels.every((label) => [noun, `${noun}s`].includes(label.toLowerCase())) ? [] : labels;
};

// One entry per node, though a node can use the reference in two fields
const usingNodes = (reference: MissingReference) => [
  ...new Map(reference.places.map((place) => [place.nodeId, place.nodeName])).values(),
];

interface MissingReferencesDialogProps {
  isOpen: boolean;
  missing: MissingReference[];
  targets: Partial<Record<ReferenceKind, ReferenceTarget[]>>;
  onCancel: () => void;
  onUpload: (replacements: ReferenceReplacement[]) => void;
}

export const MissingReferencesDialog: React.FC<MissingReferencesDialogProps> = ({
  isOpen,
  missing,
  targets,
  onCancel,
  onUpload,
}) => {
  const bodyRef = useRef<HTMLDivElement>(null);
  // Picked target ids per reference, then per place
  const [picks, setPicks] = useState<Record<string, Record<string, string[]>>>({});
  const [separate, setSeparate] = useState<Record<string, boolean>>({});

  const optionsFor = (reference: MissingReference, places: ReferencePlace[]) =>
    acceptedTargets(
      targets[reference.kind] ?? [],
      places.map((place) => place.field)
    );

  const pickFor = (reference: MissingReference, place: ReferencePlace) =>
    picks[referenceKey(reference)]?.[placeKey(place)] ?? [];

  const pick = (reference: MissingReference, places: ReferencePlace[], ids: string[]) =>
    setPicks((prev) => {
      const next = { ...prev[referenceKey(reference)] };
      for (const place of places) next[placeKey(place)] = ids;
      return { ...prev, [referenceKey(reference)]: next };
    });

  const setSameForAll = (reference: MissingReference, same: boolean) => {
    setSeparate((prev) => ({ ...prev, [referenceKey(reference)]: !same }));
    if (!same) return;
    const first =
      reference.places.map((place) => pickFor(reference, place)).find((ids) => ids.length > 0) ?? [];
    const fitting = optionsFor(reference, reference.places).map((target) => target.id);
    pick(reference, reference.places, first.filter((id) => fitting.includes(id)));
  };

  const isDone = (reference: MissingReference) =>
    reference.places.every((place) => pickFor(reference, place).length > 0);
  const remaining = missing.filter((reference) => !isDone(reference)).length;

  const handleUpload = () => {
    const replacements = missing.flatMap((reference) =>
      reference.places.flatMap((place): ReferenceReplacement[] => {
        const ids = pickFor(reference, place);
        const to = (targets[reference.kind] ?? []).filter((target) => ids.includes(target.id));
        return to.length > 0
          ? [{ nodeId: place.nodeId, field: place.field, from: reference.ids, to }]
          : [];
      })
    );
    onUpload(replacements);
  };

  const kinds = (Object.keys(REFERENCE_KIND_NOUNS) as ReferenceKind[]).filter((kind) =>
    missing.some((reference) => reference.kind === kind)
  );

  const renderReference = (reference: MissingReference) => {
    const key = referenceKey(reference);
    const Picker = reference.multiple ? TargetMultiSelect : TargetSelect;
    const shared = optionsFor(reference, reference.places);
    // Places with options of their own but none in common start apart.
    const apart =
      shared.length === 0 &&
      reference.places.some((place) => optionsFor(reference, [place]).length > 0);
    const canSplit = reference.places.length > 1;
    const isSeparate = canSplit && (separate[key] ?? apart);
    const nodes = usingNodes(reference);
    const title =
      nodes.length > 1
        ? `${nodes[0]} and ${countLabel(nodes.length - 1, "other node")}`
        : nodes[0];
    const fields = fieldLabels(reference);
    const notes = [
      ...(!isSeparate && fields.length > 0 ? [fields.join(", ")] : []),
      ...(reference.name ? [`was ${reference.name}`] : []),
    ];
    return (
      <div key={key} className="px-4 py-3">
        <div className="flex items-center gap-3">
          <StatusIcon done={isDone(reference)} />
          <div className="min-w-0 flex-1">
            {nodes.length > 1 ? (
              <Tooltip>
                <TooltipTrigger asChild>
                  <p className="w-fit max-w-full cursor-default truncate text-sm font-medium">
                    {title}
                  </p>
                </TooltipTrigger>
                <TooltipContent align="start" className="max-w-xs">
                  <ul className="space-y-0.5">
                    {nodes.map((name, i) => (
                      <li key={i}>{name}</li>
                    ))}
                  </ul>
                </TooltipContent>
              </Tooltip>
            ) : (
              <p className="truncate text-sm font-medium" title={title}>
                {title}
              </p>
            )}
            {(notes.length > 0 || canSplit) && (
              <div className="flex min-w-0 gap-1 text-xs text-muted-foreground">
                {notes.length > 0 && <span className="truncate">{notes.join(" · ")}</span>}
                {canSplit && (
                  <span className="shrink-0">
                    {notes.length > 0 && "· "}
                    <LinkButton onClick={() => setSameForAll(reference, isSeparate)}>
                      {isSeparate ? "Use one for all" : "Choose separately"}
                    </LinkButton>
                  </span>
                )}
              </div>
            )}
          </div>
          {!isSeparate && (
            <Picker
              options={shared}
              value={pickFor(reference, reference.places[0])}
              onChange={(ids) => pick(reference, reference.places, ids)}
              label={`Replacement for ${title}`}
            />
          )}
        </div>
        {isSeparate && (
          <div className="mt-3 space-y-2 pl-7">
            {reference.places.map((place) => (
              <div key={placeKey(place)} className="flex items-center gap-3">
                <p className="min-w-0 flex-1 truncate text-sm">
                  {place.nodeName}
                  {fields.length > 0 && (
                    <span className="text-muted-foreground"> · {place.field.label}</span>
                  )}
                </p>
                <Picker
                  options={optionsFor(reference, [place])}
                  value={pickFor(reference, place)}
                  onChange={(ids) => pick(reference, [place], ids)}
                  label={`Replacement for ${place.nodeName} ${place.field.label}`}
                />
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onCancel()}>
      <DialogContent
        className="flex max-h-[85vh] max-w-2xl flex-col overflow-hidden p-0"
        // Start on the first usable picker rather than a link.
        onOpenAutoFocus={(event) => {
          const picker = bodyRef.current?.querySelector<HTMLElement>(
            '[role="combobox"]:not(:disabled)'
          );
          if (!picker) return;
          event.preventDefault();
          picker.focus();
        }}
      >
        <DialogHeader className="mb-0 shrink-0 p-6 pb-4">
          <DialogTitle>Some items aren't in this environment</DialogTitle>
          <DialogDescription>
            Choose what this workflow should use instead, or set them up later in their
            nodes.
          </DialogDescription>
        </DialogHeader>

        <TooltipProvider delayDuration={200}>
          <div ref={bodyRef} className="min-h-0 flex-1 space-y-5 overflow-y-auto px-6 pb-6">
            {kinds.map((kind) => (
              <section key={kind} className="space-y-2">
                <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {sectionTitle(kind)}
                </h3>
                <div className="divide-y rounded-xl border">
                  {missing.filter((reference) => reference.kind === kind).map(renderReference)}
                </div>
              </section>
            ))}
          </div>
        </TooltipProvider>

        <DialogFooter className="shrink-0 gap-2 border-t px-6 py-4 sm:items-center sm:justify-between sm:space-x-0">
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <StatusIcon done={remaining === 0} />
            {remaining === 0
              ? "All replaced"
              : `${missing.length - remaining} of ${missing.length} replaced`}
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onCancel}>
              Cancel
            </Button>
            {remaining > 0 && (
              <Button variant="secondary" onClick={handleUpload}>
                {remaining < missing.length ? "Set up the rest later" : "Set up later"}
              </Button>
            )}
            <Button onClick={handleUpload} disabled={remaining > 0}>
              Upload
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
