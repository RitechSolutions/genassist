import * as React from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Input } from "@/components/input";

interface TimePickerProps {
  date: Date | undefined;
  onChange: (time: { hour: number; minute: number }) => void;
}

export function TimePicker({ date, onChange }: TimePickerProps) {
  const [hour, setHour] = React.useState(date ? date.getHours() : 0);
  const [minute, setMinute] = React.useState(date ? date.getMinutes() : 0);

  React.useEffect(() => {
    if (date) {
      setHour(date.getHours());
      setMinute(date.getMinutes());
    }
  }, [date]);

  const handleHourChange = (value: string) => {
    const newHour = parseInt(value, 10);
    if (!isNaN(newHour) && newHour >= 0 && newHour <= 23) {
      setHour(newHour);
      onChange({ hour: newHour, minute });
    }
  };

  const handleMinuteChange = (value: string) => {
    const newMinute = parseInt(value, 10);
    if (!isNaN(newMinute) && newMinute >= 0 && newMinute <= 59) {
      setMinute(newMinute);
      onChange({ hour, minute: newMinute });
    }
  };

  return (
    <div className="flex items-center justify-around">
      <Input
        type="number"
        value={String(hour).padStart(2, "0")}
        onChange={(e) => handleHourChange(e.target.value)}
        className="w-[80px]"
        min="0"
        max="23"
      />
      <span>:</span>
      <Input
        type="number"
        value={String(minute).padStart(2, "0")}
        onChange={(e) => handleMinuteChange(e.target.value)}
        className="w-[80px]"
        min="0"
        max="59"
      />
    </div>
  );
} 