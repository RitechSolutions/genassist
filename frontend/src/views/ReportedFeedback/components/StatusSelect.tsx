import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";

import { FeedbackStatus } from "@/services/reportedFeedback";
import { STATUS_META, STATUS_ORDER } from "../constants";

type StatusSelectProps = {
  value: FeedbackStatus;
  onChange: (status: FeedbackStatus) => void;
  className?: string;
};

/** A pill-styled status dropdown shared by the table rows and the detail dialog. */
export function StatusSelect({ value, onChange, className }: StatusSelectProps) {
  return (
    <Select value={value} onValueChange={(v) => onChange(v as FeedbackStatus)}>
      <SelectTrigger
        className={`h-8 w-[150px] rounded-full border text-xs font-medium ${STATUS_META[value].className} ${className ?? ""}`}
      >
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {STATUS_ORDER.map((status) => (
          <SelectItem key={status} value={status}>
            {STATUS_META[status].label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
