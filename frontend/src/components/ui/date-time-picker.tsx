import * as React from "react";
import { format, setHours, setMinutes } from "date-fns";
import { Calendar as CalendarIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/button";
import { Calendar } from "@/components/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/popover";
import { TimePicker } from "./time-picker";

interface DateTimePickerProps {
  date: Date | undefined;
  setDate: (date: Date | undefined) => void;
  disabled?: (date: Date) => boolean;
}

export function DateTimePicker({ date, setDate, disabled }: DateTimePickerProps) {
  const handleDateSelect = (selectedDate: Date | undefined) => {
    if (selectedDate) {
      const newDateWithTime = date
        ? setMinutes(setHours(selectedDate, date.getHours()), date.getMinutes())
        : selectedDate;
      setDate(newDateWithTime);
    } else {
      setDate(undefined);
    }
  };

  const handleTimeChange = (time: { hour: number; minute: number }) => {
    if (date) {
      const newDate = setMinutes(setHours(date, time.hour), time.minute);
      setDate(newDate);
    }
  };

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant={"outline"}
          className={cn(
            "w-full justify-start text-left font-normal",
            !date && "text-muted-foreground"
          )}
        >
          <CalendarIcon className="mr-2 h-4 w-4" />
          {date ? format(date, "yyyy-MM-dd HH:mm") : <span>Pick a date</span>}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0">
        <Calendar
          mode="single"
          selected={date}
          onSelect={handleDateSelect}
          initialFocus
          disabled={disabled}
        />
        <div className="p-4 border-t border-border">
          <TimePicker
            date={date}
            onChange={handleTimeChange}
          />
        </div>
      </PopoverContent>
    </Popover>
  );
} 