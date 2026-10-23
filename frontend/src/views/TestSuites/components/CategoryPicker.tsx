import React, { useState } from "react";
import { Check, ChevronsUpDown, Plus, X } from "lucide-react";
import { Button } from "@/components/button";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/popover";
import { cn } from "@/helpers/utils";
import { CATEGORY_MAX_LENGTH, pickerChoices } from "../helpers/categories";

interface CategoryPickerProps {
  id?: string;
  /** "" when none is set. */
  value: string;
  onChange: (value: string) => void;
  categories: string[];
}

/** Picks a category already in use or adds one by typing it. */
export const CategoryPicker: React.FC<CategoryPickerProps> = ({ id, value, onChange, categories }) => {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const { typed, isNew, shown } = pickerChoices(text, value, categories);

  const pick = (name: string) => {
    onChange(name);
    setOpen(false);
    setText("");
  };

  return (
    // Modal, so the wheel scrolls its list inside the dataset dialog, whose scroll lock would block it.
    <Popover
      modal
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) setText("");
      }}
    >
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between bg-background font-normal"
        >
          <span className={cn("truncate", !value && "text-muted-foreground")}>{value || "No category"}</span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" aria-hidden="true" />
        </Button>
      </PopoverTrigger>
      {/* Above the dialogs it can open in, as the selects are. */}
      <PopoverContent className="z-[1400] w-[--radix-popover-trigger-width] p-0" align="start">
        {/* Filtered by pickerChoices: cmdk's own filter hides "Add" when the text has extra spaces. */}
        <Command shouldFilter={false}>
          <CommandInput
            placeholder="Find or add a category"
            value={text}
            onValueChange={(next) => setText(next.slice(0, CATEGORY_MAX_LENGTH))}
          />
          <CommandList>
            <CommandEmpty>Type a name to add a category.</CommandEmpty>
            <CommandGroup>
              {/* Values carry a prefix, so a category named like an action is still a category. */}
              {shown.map((name) => (
                <CommandItem key={name} value={`category:${name}`} onSelect={() => pick(name)}>
                  <Check
                    className={cn("mr-2 h-4 w-4", value === name ? "opacity-100" : "opacity-0")}
                    aria-hidden="true"
                  />
                  <span className="truncate">{name}</span>
                </CommandItem>
              ))}
              {/* After the matches, so Enter reuses a category rather than adding a near copy. */}
              {isNew && (
                <CommandItem value="action:add" onSelect={() => pick(typed)}>
                  <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
                  Add “{typed}”
                </CommandItem>
              )}
              {value && !typed && (
                <CommandItem value="action:clear" onSelect={() => pick("")}>
                  <X className="mr-2 h-4 w-4" aria-hidden="true" />
                  No category
                </CommandItem>
              )}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
};
