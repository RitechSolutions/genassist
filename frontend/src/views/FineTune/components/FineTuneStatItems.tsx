import { ReactNode } from "react";

type StatItemProps = {
  label: string;
  value: ReactNode;
};

export function StatItem({ label, value }: StatItemProps) {
  return (
    <div className="rounded-lg bg-muted px-4 py-3 flex flex-col gap-1 min-h-[86px]">
      <span className="text-xs text-muted-foreground">{label}</span>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}

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