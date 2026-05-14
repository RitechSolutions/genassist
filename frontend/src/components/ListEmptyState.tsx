import type { ReactNode } from "react";

export type ListEmptyStateProps = {
  icon: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
};

export function ListEmptyState({
  icon,
  title,
  description,
  action,
}: ListEmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-4 text-center">
      <div className="rounded-full bg-gray-100 p-4">{icon}</div>
      <h3 className="font-medium text-lg">{title}</h3>
      <p className="text-sm text-gray-500 max-w-sm px-4">{description}</p>
      {action}
    </div>
  );
}
