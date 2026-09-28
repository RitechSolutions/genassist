import { FC, useState, useEffect, useLayoutEffect, useRef } from "react";
import { Button } from "@/components/button";
import { Plus, Info } from "lucide-react";
import { RichInput } from "@/components/richInput";
import { RichTextarea } from "@/components/richTextarea";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/select";
import { Badge } from "@/components/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/dialog";
import { Checkbox } from "@/components/checkbox";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/RadixTooltip";
import { NodeSchema, SchemaField, SchemaType } from "../../types/schemas";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/dropdown-menu";
import { useChatInputSchema } from "../../hooks/useChatInputSchema";
import { Label } from "@/components/label";

interface ParameterSectionProps {
  label?: string;
  dynamicParams: NodeSchema;
  setDynamicParams: React.Dispatch<React.SetStateAction<NodeSchema>>;
  addItem: (
    setter: React.Dispatch<React.SetStateAction<NodeSchema>>,
    template: SchemaField
  ) => void;
  removeItem: (
    setter: React.Dispatch<React.SetStateAction<NodeSchema>>,
    name: string
  ) => void;
  suggestParams?: boolean;
  listSuggestedParams?: NodeSchema;
  allowStateful?: boolean; // Only allow stateful parameters in chatInputNode
  allowFilter?: boolean; // Show "Use in filter" checkbox for filtering & analytics
  allowHidden?: boolean; // Show "Hidden" checkbox to mask the value in persisted data
}

interface ParameterDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  paramName: string | null;
  param: SchemaField | null;
  onSave: (name: string, param: SchemaField) => void;
  onDelete?: (name: string) => void;
  mode: "edit" | "create";
  totalParams: number;
  suggestedParams?: NodeSchema;
  allowStateful?: boolean; // Only allow stateful parameters in chatInputNode
  allowFilter?: boolean; // Show "Use in filter" checkbox
  allowHidden?: boolean; // Show "Hidden" checkbox
}

interface ParameterBadgesProps {
  params: Record<string, { type: string; required?: boolean }>;
  className?: string;
  /**
   * Clip the badges to a single row and summarise the rest as a "+N" circle.
   * Used on canvas nodes, whose width is fixed: a long variable list would
   * otherwise wrap into several rows and make the node very tall.
   */
  collapse?: boolean;
}

interface BadgeEntry {
  name: string;
  suggested: boolean;
}

// Matches the `gap-2` of the badge row.
const BADGE_GAP = 8;
// Fallback width for the "+N" circle if it can't be measured.
const COUNTER_FALLBACK_WIDTH = 32;

/**
 * Renders as many badges as fit on the first row, followed by a "+N" circle
 * standing for the ones left out. The fit is measured from the real layout
 * (first paint renders every badge, hidden behind a layout effect) so the row
 * stays full whatever the badge lengths are.
 */
const CollapsedParameterBadges: FC<{
  entries: BadgeEntry[];
  className?: string;
}> = ({ entries, className = "" }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const measuredWidthRef = useRef(0);
  // `null` means "measuring": everything is rendered so the rows can be read.
  const [visibleCount, setVisibleCount] = useState<number | null>(null);
  // Bumped to force a fresh measuring pass (see the resize observer below).
  const [measureKey, setMeasureKey] = useState(0);

  // The parent keys this component on the variable list, so a changed list
  // remounts it and measuring starts over.
  useLayoutEffect(() => {
    if (visibleCount !== null) return;
    const container = containerRef.current;
    if (!container || container.clientWidth === 0) return;

    const children = Array.from(container.children) as HTMLElement[];
    const badges = children.slice(0, entries.length);
    if (badges.length === 0) return;
    measuredWidthRef.current = container.clientWidth;

    const firstRowTop = badges[0].offsetTop;
    let count = badges.filter((badge) => badge.offsetTop === firstRowTop).length;

    if (count < badges.length) {
      // Something will be hidden, so the row must also fit the "+N" circle
      // (rendered last during the measuring pass).
      const counter = children[entries.length];
      const counterWidth = counter?.offsetWidth || COUNTER_FALLBACK_WIDTH;
      while (count > 1) {
        const last = badges[count - 1];
        const rowEnd = last.offsetLeft + last.offsetWidth;
        if (rowEnd + BADGE_GAP + counterWidth <= container.clientWidth) break;
        count -= 1;
      }
    }

    setVisibleCount(count);
  }, [visibleCount, entries.length, measureKey]);

  // The node width is fixed today, but re-measure if it ever changes (or if the
  // node was laid out while off-screen, i.e. at zero width).
  useEffect(() => {
    const container = containerRef.current;
    if (!container || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => {
      const width = containerRef.current?.clientWidth ?? 0;
      if (width !== 0 && width !== measuredWidthRef.current) {
        setVisibleCount(null);
        setMeasureKey((key) => key + 1);
      }
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  const isMeasuring = visibleCount === null;
  const visible = isMeasuring ? entries : entries.slice(0, visibleCount);
  const hidden = entries.slice(visible.length);
  // During the measuring pass the counter is only there to be measured, so its
  // label just needs the right order of magnitude.
  const hiddenCount = isMeasuring ? entries.length - 1 : hidden.length;

  return (
    <div
      ref={containerRef}
      className={`flex gap-2 overflow-hidden ${
        isMeasuring ? "flex-wrap" : "flex-nowrap"
      } ${className}`}
    >
      {visible.map((entry) => (
        <Badge
          key={entry.name}
          variant="secondary"
          className={`shrink-0 cursor-pointer hover:bg-secondary/80 ${
            entry.suggested ? "font-light" : ""
          }`}
        >
          {entry.name}
        </Badge>
      ))}
      {hiddenCount > 0 && (
        <Badge
          variant="secondary"
          className={`shrink-0 h-[22px] min-w-[22px] justify-center px-1.5 ${
            isMeasuring ? "invisible" : ""
          }`}
          title={hidden.map((entry) => entry.name).join("\n")}
        >
          +{hiddenCount}
        </Badge>
      )}
    </div>
  );
};

export const ParameterBadges: FC<ParameterBadgesProps> = ({
  params,
  className = "",
  collapse = false,
}) => {
  const chatInputSchema = useChatInputSchema();
  const suggestedParams = chatInputSchema || {};
  const names = Object.keys(params ?? {});
  // Suggested params keep their place at the end of the list.
  const entries: BadgeEntry[] = [
    ...names
      .filter((name) => !suggestedParams[name])
      .map((name) => ({ name, suggested: false })),
    ...names
      .filter((name) => suggestedParams[name])
      .map((name) => ({ name, suggested: true })),
  ];

  if (entries.length === 0) {
    return (
      <div className={`flex flex-wrap gap-2 ${className}`}>
        <span className="text-sm text-muted-foreground italic">
          No variables required
        </span>
      </div>
    );
  }

  if (collapse) {
    return (
      <CollapsedParameterBadges
        key={entries.map((entry) => entry.name).join("|")}
        entries={entries}
        className={className}
      />
    );
  }

  return (
    <div className={`flex flex-wrap gap-2 ${className}`}>
      {entries.map((entry) => (
        <Badge
          key={entry.name}
          variant="secondary"
          className={`cursor-pointer hover:bg-secondary/80 ${
            entry.suggested ? "font-light" : ""
          }`}
        >
          {entry.name}
        </Badge>
      ))}
    </div>
  );
};

const ParameterDialog: FC<ParameterDialogProps> = ({
  isOpen,
  onOpenChange,
  paramName,
  param,
  onSave,
  onDelete,
  mode,
  totalParams,
  allowStateful = false,
  allowFilter = false,
  allowHidden = false,
}) => {
  const [formData, setFormData] = useState<{
    name: string;
    type: SchemaType;
    description: string;
    required: boolean;
    defaultValue?: string;
    stateful?: boolean;
    useInFilter?: boolean;
    hidden?: boolean;
  }>({
    name: "",
    type: "string",
    description: "",
    required: false,
    defaultValue: "",
    stateful: false,
    useInFilter: false,
    hidden: false,
  });

  useEffect(() => {
    if (isOpen) {
      if (paramName && param) {
        setFormData({
          name: paramName,
          type: param.type,
          description: param.description || "",
          required: param.required || false,
          defaultValue: param.defaultValue || "",
          // Only preserve stateful if allowStateful is true, otherwise reset to false
          stateful: allowStateful ? (param.stateful || false) : false,
          useInFilter: allowFilter ? (param.useInFilter || false) : false,
          hidden: allowHidden ? (param.hidden || false) : false,
        });
      } else {
        setFormData({
          name: "",
          type: "string",
          description: "",
          required: false,
          defaultValue: "",
          stateful: false,
          useInFilter: false,
          hidden: false,
        });
      }
    }
  }, [isOpen, mode, paramName, param, allowStateful, allowFilter, allowHidden]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave(formData.name, {
      type: formData.type,
      description: formData.description,
      required: formData.required,
      defaultValue: formData.defaultValue,
      stateful: allowStateful ? formData.stateful : false,
      useInFilter: allowFilter ? formData.useInFilter : false,
      hidden: allowHidden ? formData.hidden : false,
    });
    onOpenChange(false);
  };

  const handleDelete = () => {
    if (paramName && onDelete) {
      onDelete(paramName);
      onOpenChange(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent style={{ zIndex: 1100 }}>
        <DialogHeader>
          <DialogTitle>{mode === 'create' ? 'Add Parameter' : 'Edit Parameter'}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Parameter Name</label>
            <RichInput
              placeholder="param_1"
              value={formData.name}
              onChange={(e) => setFormData((prev) => ({ ...prev, name: e.target.value }))}
              className="w-full"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Type</label>
            <Select
              value={formData.type}
              onValueChange={(v) => setFormData((prev) => ({ ...prev, type: v as SchemaType }))}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {['string', 'number', 'boolean', 'object', 'array', 'any'].map((t) => (
                  <SelectItem key={t} value={t}>
                    {t.charAt(0).toUpperCase() + t.slice(1)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Description</label>
            <RichTextarea
              size="hint"
              placeholder="Parameter description"
              value={formData.description}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  description: e.target.value,
                }))
              }
              className="w-full"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Required</label>
            <Select
              value={formData.required ? 'true' : 'false'}
              onValueChange={(v) =>
                setFormData((prev) => ({
                  ...prev,
                  required: v === 'true',
                  defaultValue: v === 'true' ? '' : prev.defaultValue,
                }))
              }
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="true">Yes</SelectItem>
                <SelectItem value="false">No</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {allowStateful && (
            <div className="space-y-2">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="stateful"
                  checked={formData.stateful || false}
                  onCheckedChange={(checked) => setFormData((prev) => ({ ...prev, stateful: checked === true }))}
                />
                <label htmlFor="stateful" className="text-sm font-medium cursor-pointer">
                  Stateful (persists across workflow executions)
                </label>
              </div>
              <p className="text-xs text-muted-foreground">
                When enabled, this parameter will maintain its value between workflow executions
              </p>
            </div>
          )}
          {allowFilter && (
            <div className="space-y-2">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="useInFilter"
                  checked={formData.useInFilter || false}
                  onCheckedChange={(checked) => setFormData((prev) => ({ ...prev, useInFilter: checked === true }))}
                />
                <label htmlFor="useInFilter" className="text-sm font-medium cursor-pointer">
                  Use in filter (available for filtering & analytics)
                </label>
              </div>
              <p className="text-xs text-muted-foreground">
                When enabled, this parameter will be stored as a custom attribute on conversations for filtering and
                analytics
              </p>
            </div>
          )}
          {allowHidden && (
            <div className="space-y-2">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="hidden"
                  checked={formData.hidden || false}
                  onCheckedChange={(checked) => setFormData((prev) => ({ ...prev, hidden: checked === true }))}
                />
                <label htmlFor="hidden" className="text-sm font-medium cursor-pointer">
                  Hidden (value masked in saved data &amp; logs)
                </label>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className="inline-flex rounded-full text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                        aria-label="Hidden parameter info"
                      >
                        <Info className="h-4 w-4" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-balance">
                      Masking replaces the value wherever it appears in saved text, so pick a
                      distinctive value. Very short or common values (e.g. a single digit or a word
                      like &quot;yes&quot;) can collide with unrelated text. For that reason, values
                      shorter than 2 characters are not masked.
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
              <p className="text-xs text-muted-foreground">
                When enabled, this parameter is still used at runtime, but its value is stored as
                [{(formData.name || "PARAM_NAME").toUpperCase()}] in messages, response logs and custom attributes
              </p>
            </div>
          )}
          {!formData.required && (
            <div className="space-y-2">
              <label className="text-sm font-medium">Default Value</label>
              <RichInput
                placeholder="Default value (optional)"
                value={formData.defaultValue || ''}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    defaultValue: e.target.value,
                  }))
                }
                className="w-full"
              />
            </div>
          )}
          <DialogFooter className="flex justify-between">
            {mode === 'edit' && onDelete && (
              <Button
                type="button"
                variant="destructive"
                onClick={handleDelete}
                // disabled={totalParams <= 1}
              >
                Delete Parameter
              </Button>
            )}
            <Button type="submit" disabled={!formData.name}>
              {mode === 'create' ? 'Add Parameter' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export const ParameterSection: FC<ParameterSectionProps> = ({
  label,
  dynamicParams,
  setDynamicParams,
  addItem,
  removeItem,
  suggestParams = false,
  listSuggestedParams = {},
  allowStateful = false,
  allowFilter = false,
  allowHidden = false,
}) => {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedParamName, setSelectedParamName] = useState<string | null>(
    null
  );
  const [dialogMode, setDialogMode] = useState<"edit" | "create">("create");
  const chatInputSchema = useChatInputSchema();
  const suggestedParams = listSuggestedParams || (suggestParams ? chatInputSchema : {});
  const validDynamicParams = Object.entries(dynamicParams ?? {}).filter(
    (entry): entry is [string, SchemaField] => {
      const param = entry[1];
      return Boolean(param && typeof param === "object");
    }
  );
  const handleParamClick = (name: string) => {
    setSelectedParamName(name);
    setDialogMode("edit");
    setDialogOpen(true);
  };

  // Handles adding a suggested param or opening dialog for new
  const handleAddSelect = (selected: string) => {
    if (selected === "__add_new__") {
      setSelectedParamName(null);
      setDialogMode("create");
      setDialogOpen(true);
    } else if (suggestedParams?.[selected]) {
      setDynamicParams((prev) => ({
        ...prev,
        [selected]: suggestedParams[selected],
      }));
    }
  };

  const handleSave = (name: string, paramData: SchemaField) => {
    if (dialogMode === "create") {
      setDynamicParams((prev) => ({
        ...prev,
        [name]: paramData,
      }));
    } else if (selectedParamName) {
      setDynamicParams((prev) => {
        const newParams = { ...prev };
        if (name !== selectedParamName) {
          delete newParams[selectedParamName];
        }
        newParams[name] = paramData;
        return newParams;
      });
    }
  };

  const handleDelete = (name: string) => {
    removeItem(setDynamicParams, name);
  };

  return (
    <div className="flex flex-col gap-1 py-1 w-full min-w-0">
      {label && <Label htmlFor="parameters">{label}</Label>}

      <div className="flex flex-wrap gap-2 items-center min-w-0">
        {validDynamicParams
          .filter(([name, param]) => !suggestedParams[name])
          .map(([name, param]) => (
            <Badge
              key={name}
              variant="secondary"
              className={`cursor-pointer hover:bg-secondary/80 break-words ${param.stateful ? 'bg-blue-500 text-white' : ''}`}
              onClick={() => handleParamClick(name)}
            >
              {name}
            </Badge>
          ))}
        {validDynamicParams
          .filter(([name, param]) => suggestedParams[name])
          .map(([name, param]) => (
            <Badge
              key={name}
              variant="secondary"
              className="cursor-pointer hover:bg-secondary/80 font-light break-words"
              onClick={() => handleParamClick(name)}
            >
              {name}
            </Badge>
          ))}
        {/* Add Parameter DropdownMenu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="p-0 border-none bg-none outline-none"
              style={{ background: "none" }}
            >
              <Badge
                variant="outline"
                className="cursor-pointer hover:bg-secondary/80 flex items-center gap-1"
              >
                <Plus className="w-3 h-3" />
                Add Parameter
              </Badge>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" style={{ zIndex: 1100 }}>
            {Object.entries(suggestedParams || {}).map(([name, s]) => (
              <DropdownMenuItem
                key={name}
                onSelect={() => handleAddSelect(name)}
                className="break-words"
              >
                {name} ({s.type}) - {s.description}
              </DropdownMenuItem>
            ))}
            <DropdownMenuItem
              onSelect={() => handleAddSelect("__add_new__")}
              className="font-semibold"
            >
              + Add new...
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <ParameterDialog
        isOpen={dialogOpen}
        onOpenChange={setDialogOpen}
        paramName={selectedParamName}
        param={selectedParamName ? dynamicParams?.[selectedParamName] ?? null : null}
        onSave={handleSave}
        onDelete={handleDelete}
        mode={dialogMode}
        totalParams={Object.keys(dynamicParams ?? {}).length}
        allowStateful={allowStateful}
        allowFilter={allowFilter}
        allowHidden={allowHidden}
      />
    </div>
  );
};
