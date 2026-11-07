import React from "react";
import { Check } from "lucide-react";
import { Button } from "@/components/button";
import { CommandItem } from "@/components/command";
import { cn } from "@/helpers/utils";
import { ReferenceTarget } from "../utils/workflowReferences";

interface TargetOptionProps {
  target: ReferenceTarget;
  checked: boolean;
  onToggle: () => void;
}

// Drawn like the Checkbox component, but not a control: the row handles the click.
const CheckboxMark: React.FC<{ checked: boolean }> = ({ checked }) => (
  <span
    aria-hidden="true"
    className={cn(
      "mr-2 flex h-4 w-4 shrink-0 items-center justify-center rounded-sm border border-primary",
      checked && "bg-primary text-primary-foreground"
    )}
  >
    {checked && <Check className="h-4 w-4" />}
  </span>
);

export const TargetOption: React.FC<TargetOptionProps> = ({ target, checked, onToggle }) => (
  <CommandItem value={target.id} keywords={[target.label]} onSelect={onToggle} aria-checked={checked}>
    <CheckboxMark checked={checked} />
    <span className="truncate">{target.label}</span>
  </CommandItem>
);

interface PickerFooterProps {
  onClear: () => void;
  onDone: () => void;
}

// Outside the list, so search and Enter never clear the picks.
export const PickerFooter: React.FC<PickerFooterProps> = ({ onClear, onDone }) => (
  <div className="flex items-center justify-between border-t p-2">
    <Button type="button" size="sm" variant="ghost" onClick={onClear}>
      Clear selection
    </Button>
    <Button type="button" size="sm" onClick={onDone}>
      Done
    </Button>
  </div>
);
