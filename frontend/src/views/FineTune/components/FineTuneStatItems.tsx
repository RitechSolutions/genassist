import { ReactNode } from "react";

type DetailItemProps = {
  label: string;
  value: ReactNode;
};

export function DetailItem({ label, value }: DetailItemProps) {
  return (
    <div className="rounded-md bg-muted px-4 py-3 flex flex-col gap-1">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-sm font-medium text-foreground">{value}</span>
    </div>
  );
}