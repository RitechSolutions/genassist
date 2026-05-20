import { Skeleton } from "@/components/skeleton";
import { cn } from "@/helpers/utils";

export type PageListSkeletonVariant =
  | "standard"
  | "rich"
  | "evaluation"
  | "agent"
  | "operator"
  | "conversation"
  | "dashboard-agent"
  | "dashboard-integration";

export interface PageListSkeletonProps {
  rows?: number;
  variant?: PageListSkeletonVariant;
  className?: string;
  /** When false, only the row list is rendered (no outer bordered container). */
  bordered?: boolean;
}

function PageListSkeletonRow({ variant }: { variant: PageListSkeletonVariant }) {
  if (variant === "operator") {
    return (
      <div className="flex items-center gap-3 p-2">
        <Skeleton className="h-10 w-10 rounded-full shrink-0" />
        <div className="flex-1 min-w-0 space-y-2">
          <Skeleton className="h-4 w-32" />
          <div className="flex items-center gap-3">
            <Skeleton className="h-3 w-12" />
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-3 w-10" />
          </div>
        </div>
        <Skeleton className="h-3 w-14 shrink-0" />
      </div>
    );
  }

  if (variant === "dashboard-agent") {
    return (
      <div className="flex gap-3 items-center p-2">
        <div className="flex flex-col gap-1.5 flex-1 min-w-0">
          <Skeleton className="h-4 w-32" />
          <div className="flex gap-3 items-center flex-wrap">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-3 w-14" />
            <Skeleton className="h-3 w-12" />
          </div>
        </div>
      </div>
    );
  }

  if (variant === "dashboard-integration") {
    return (
      <div className="flex gap-3 items-center p-2">
        <Skeleton className="h-10 w-10 rounded-lg shrink-0" />
        <div className="flex flex-col flex-1 min-w-0 gap-1.5">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-3 w-40" />
        </div>
      </div>
    );
  }

  if (variant === "conversation") {
    return (
      <div className="p-4 sm:p-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex min-w-0 flex-1 items-start gap-3 sm:gap-4">
            <Skeleton className="h-9 w-9 rounded-lg shrink-0" />
            <div className="min-w-0 flex-1 space-y-2">
              <Skeleton className="h-5 w-52" />
              <Skeleton className="h-4 w-64" />
              <div className="flex flex-wrap gap-2">
                <Skeleton className="h-5 w-14 rounded-full" />
                <Skeleton className="h-5 w-14 rounded-full" />
                <Skeleton className="h-5 w-14 rounded-full" />
              </div>
              <Skeleton className="h-4 w-full max-w-md" />
            </div>
          </div>
          <Skeleton className="h-6 w-20 rounded-full shrink-0" />
        </div>
      </div>
    );
  }

  return (
    <div className="py-4 px-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex-1 space-y-2">
          {variant === "agent" ? (
            <div className="flex items-center gap-2">
              <Skeleton className="h-6 w-40" />
              <Skeleton className="h-5 w-14 rounded-full" />
            </div>
          ) : (
            <Skeleton className="h-6 w-48" />
          )}
          <Skeleton className="h-4 w-64" />
          {variant === "rich" && <Skeleton className="h-4 w-40" />}
          {variant === "agent" && (
            <>
              <Skeleton className="h-4 w-72" />
              <Skeleton className="h-4 w-56" />
            </>
          )}
          {variant === "standard" && (
            <Skeleton className="h-3 w-32 mt-2" />
          )}
          {variant === "evaluation" && (
            <>
              <div className="flex items-center gap-2 mt-2">
                <Skeleton className="h-2 w-32 rounded-full" />
                <Skeleton className="h-4 w-16" />
              </div>
              <div className="flex gap-1 mt-2">
                <Skeleton className="h-5 w-20 rounded-full" />
                <Skeleton className="h-5 w-16 rounded-full" />
              </div>
            </>
          )}
        </div>
        <div className="flex items-center justify-end gap-2 sm:gap-4">
          {variant === "agent" ? (
            <>
              <Skeleton className="h-6 w-11 rounded-full" />
              <Skeleton className="h-8 w-8 rounded" />
            </>
          ) : (
            <>
              {variant === "standard" && (
                <Skeleton className="h-6 w-16 rounded-md" />
              )}
              <Skeleton className="h-8 w-8 rounded" />
              <Skeleton className="h-8 w-8 rounded" />
              {variant === "evaluation" ? (
                <Skeleton className="h-8 w-20 rounded" />
              ) : (
                <Skeleton className="h-8 w-8 rounded" />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

const COMPACT_VARIANTS: PageListSkeletonVariant[] = [
  "operator",
  "dashboard-agent",
  "dashboard-integration",
];

export function PageListSkeleton({
  rows = 3,
  variant = "standard",
  className,
  bordered = true,
}: PageListSkeletonProps) {
  const content = (
    <div
      className={
        COMPACT_VARIANTS.includes(variant)
          ? "space-y-2"
          : variant === "conversation"
            ? "divide-y divide-border"
            : "divide-y divide-gray-100"
      }
    >
      {Array.from({ length: rows }, (_, i) => (
        <PageListSkeletonRow key={i} variant={variant} />
      ))}
    </div>
  );

  if (!bordered) {
    return <div className={className}>{content}</div>;
  }

  return (
    <div
      className={cn(
        "rounded-lg border bg-white overflow-hidden",
        className
      )}
    >
      {content}
    </div>
  );
}
