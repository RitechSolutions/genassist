import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Badge } from "@/components/badge";

import { FeedbackStatus } from "@/services/reportedFeedback";
import { IssueStatus } from "@/services/issueStatuses";
import { statusMeta, withCurrentStatus } from "../helpers/issueStatuses";

type StatusSelectProps = {
  value: FeedbackStatus;
  onChange: (status: FeedbackStatus) => void;
  statuses: IssueStatus[];
  className?: string;
};

export function StatusBadge({
  value,
  statuses,
}: Pick<StatusSelectProps, "value" | "statuses">) {
  const meta = statusMeta(statuses, value);
  return (
    <Badge variant="outline" className={meta.className}>
      {meta.label}
    </Badge>
  );
}

/** A pill-styled status dropdown shared by the table rows and the detail dialog. */
export function StatusSelect({
  value,
  onChange,
  statuses,
  className,
}: StatusSelectProps) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger
        className={`h-8 w-[150px] rounded-full border text-xs font-medium ${statusMeta(statuses, value).className} ${className ?? ""}`}
      >
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {withCurrentStatus(statuses, value).map((key) => (
          <SelectItem key={key} value={key}>
            {statusMeta(statuses, key).label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
