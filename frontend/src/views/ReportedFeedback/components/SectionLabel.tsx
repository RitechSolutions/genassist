import { ComponentType, ReactNode } from "react";

export const SECTION_LABEL_CLASS =
  "flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground";

export function SectionLabel({
  icon: Icon,
  children,
}: {
  icon: ComponentType<{ className?: string }>;
  children: ReactNode;
}) {
  return (
    <div className={`mb-1.5 ${SECTION_LABEL_CLASS}`}>
      <Icon className="h-3.5 w-3.5" />
      {children}
    </div>
  );
}
