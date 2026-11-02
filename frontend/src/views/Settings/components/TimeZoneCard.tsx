import { useState } from "react";
import { Globe } from "lucide-react";
import { Card } from "@/components/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import {
  localTimeZoneName,
  readTimeZoneMode,
  writeTimeZoneMode,
  type TimeZoneMode,
} from "@/helpers/timeZone";

export const TimeZoneCard = () => {
  const [mode, setMode] = useState<TimeZoneMode>(readTimeZoneMode);

  const choose = (next: TimeZoneMode) => {
    writeTimeZoneMode(next);
    setMode(next);
  };

  return (
    <Card className="p-4 sm:p-6 shadow-sm animate-fade-up bg-card dark:bg-zinc-900">
      <div className="flex items-center gap-3 mb-4">
        <Globe className="w-5 h-5 sm:w-6 sm:h-6 text-primary" />
        <div>
          <h2 className="text-base sm:text-lg font-semibold">Time zone</h2>
          <p className="text-xs sm:text-sm text-muted-foreground">
            How dates, times and the Today filter work in this browser
          </p>
        </div>
      </div>

      <div className="flex items-center justify-between gap-4 h-[40px]">
        <label htmlFor="time-zone-mode" className="text-sm font-medium shrink-0">
          Show dates and times in
        </label>
        <Select
          value={mode}
          onValueChange={(value) => choose(value as TimeZoneMode)}
        >
          <SelectTrigger id="time-zone-mode" className="w-1/2">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="utc">UTC</SelectItem>
            <SelectItem value="local">
              Local time ({localTimeZoneName()})
            </SelectItem>
          </SelectContent>
        </Select>
      </div>
    </Card>
  );
};
