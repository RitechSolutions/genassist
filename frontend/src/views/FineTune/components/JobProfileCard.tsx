import { ReactNode } from "react";
import { Card } from "@/components/card";

export interface ProfileRow {
  label: string;
  value: ReactNode;
}

interface JobProfileCardProps {
  /** Main rows (e.g. Created at, Completed at, Created by), each on its own line */
  rows: ProfileRow[];
  /** Optional pair to show on one line at the top (e.g. n_epochs | Batch size), styled like summary stat blocks */
  pairRows?: [ProfileRow, ProfileRow];
}

function ProfileBlock({ label, value }: ProfileRow) {
  return (
    <div className="flex flex-col gap-2 py-2 sm:py-0">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-sm font-medium text-foreground">{value}</span>
    </div>
  );
}

export function JobProfileCard({ rows, pairRows }: JobProfileCardProps) {

  return (
    <Card className="w-full px-4 py-4 sm:px-6 sm:py-6 shadow-sm bg-white animate-fade-up rounded-lg border text-card-foreground h-full">
      <div className="flex flex-col gap-1">
        {pairRows && (
          <div className="grid grid-cols-2 gap-4 sm:gap-6 pb-4 mb-4 border-b border-zinc-200">
            <div className="flex flex-col gap-2">
              <span className="text-xs text-muted-foreground">{pairRows[0].label}</span>
              <span className="text-sm font-medium text-foreground">{pairRows[0].value}</span>
            </div>
            <div className="flex flex-col gap-2 border-l border-zinc-200 pl-4 sm:pl-6">
              <span className="text-xs text-muted-foreground">{pairRows[1].label}</span>
              <span className="text-sm font-medium text-foreground">{pairRows[1].value}</span>
            </div>
          </div>
        )}
        {rows.map((row, index) => {
          const isLast = index === rows.length - 1;
          const block = <ProfileBlock key={row.label} label={row.label} value={row.value} />;
          if (isLast && rows.length > 1) {
            return (
              <div key={row.label} className="pt-4 mt-4 border-t border-zinc-200">
                {block}
              </div>
            );
          }
          return block;
        })}
      </div>
    </Card>
  );
}
