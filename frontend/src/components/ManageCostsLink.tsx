import { Coins, ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";

import { buttonVariants } from "@/components/button";
import { cn } from "@/helpers/utils";
import { useHasPermission } from "@/hooks/useHasPermission";

export function ManageCostsLink({ className }: { className?: string }) {
  const canManageCosts = useHasPermission("read:llm_provider");
  if (!canManageCosts) return null;

  return (
    <Link
      to="/llm-providers?manage=costs"
      target="_blank"
      rel="noopener noreferrer"
      className={buttonVariants({ variant: "outline", size: "sm", className: cn("shrink-0 text-foreground", className) })}
    >
      <Coins />
      Manage costs
      <ExternalLink />
      <span className="sr-only">(opens in a new tab)</span>
    </Link>
  );
}
