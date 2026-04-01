import { Badge } from "@/components/badge";
import { Card } from "@/components/card";
import { Toggle } from "@/components/toggle";
import { SettingSectionType, SettingFieldType } from "../../../interfaces/settings.interface";
import { cn } from "@/lib/utils";

interface SettingSectionProps {
  section: SettingSectionType;
  toggleStates: Record<string, boolean>;
  onToggle: (label: string) => void;
}

export const SettingSection = ({ section, toggleStates, onToggle }: SettingSectionProps) => {
  const renderField = (field: SettingFieldType) => {
    switch (field.type) {
      case "toggle":
        return (
          <Toggle
            pressed={toggleStates[field.label] || false}
            onPressedChange={() => onToggle(field.label)}
            aria-label={field.label}
            className="relative px-0 h-6 w-11 bg-zinc-200 hover:bg-zinc-300 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground rounded-full"
          >
            <span
              className="absolute left-[2px] transition-transform h-5 w-5 rounded-full bg-white data-[state=on]:translate-x-[20px]"
              data-state={toggleStates[field.label] ? 'on' : 'off'}
            />
          </Toggle>
        );
      case "select":
        return (
          <select className="rounded-full border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring">
            {field.options?.map((option) => (
              <option key={option}>{option}</option>
            ))}
          </select>
        );
      case "tags": {
        const items = Array.isArray(field.value)
          ? field.value
          : field.value != null && field.value !== ""
            ? [String(field.value)]
            : [];
        return (
          <div
            className={cn(
              "flex min-h-10 w-full flex-wrap items-center gap-1.5 rounded-full border border-input bg-background px-3 py-2 text-sm text-foreground ring-offset-background",
              "cursor-default select-none opacity-75",
              field.className
            )}
            aria-readonly="true"
            tabIndex={-1}
          >
            {items.length > 0 ? (
              items.map((text) => (
                <Badge
                  key={text}
                  variant="outline"
                  className="shrink-0 border-input bg-muted/40 font-medium focus-visible:ring-0"
                >
                  {text}
                </Badge>
              ))
            ) : (
              <span className="text-sm text-muted-foreground">—</span>
            )}
          </div>
        );
      }
      default:
        return (
          <input
            type={field.type}
            placeholder={field.placeholder}
            value={typeof field.value === "string" || typeof field.value === "number" ? field.value : undefined}
            readOnly={field.readOnly}
            className={cn("rounded-full border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-75", field.className)}
            disabled={field.readOnly}
          />
        );
    }
  };

  return (
    <Card className="p-4 sm:p-6 shadow-sm animate-fade-up bg-white">
      <div className="flex items-center gap-3 mb-4">
        <section.icon className="w-5 h-5 sm:w-6 sm:h-6 text-primary" />
        <div>
          <h2 className="text-base sm:text-lg font-semibold">{section.title}</h2>
          <p className="text-xs sm:text-sm text-muted-foreground">{section.description}</p>
        </div>
      </div>

      <div className="space-y-0">
        {section.fields.map((field) => (
          <div
            key={field.label}
            className={cn(
              "flex justify-between gap-4",
              field.type === "tags"
                ? "items-start min-h-[40px] py-1.5"
                : "items-center h-[40px]"
            )}
          >
            <label
              className={cn(
                "text-sm font-medium shrink-0",
                field.type === "tags" && "pt-2"
              )}
            >
              {field.label}
            </label>
            {renderField(field)}
          </div>
        ))}
      </div>
    </Card>
  );
};