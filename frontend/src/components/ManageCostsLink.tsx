import { Coins, ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";

import { buttonVariants } from "@/components/button";
import { useHasPermission } from "@/hooks/useHasPermission";

export function ManageCostsLink() {
  const canManageCosts = useHasPermission("read:llm_provider");
  if (!canManageCosts) return null;

  return (
    <Link
      to="/llm-providers?manage=costs"
      target="_blank"
      rel="noopener noreferrer"
      className={buttonVariants({ variant: "outline", size: "sm", className: "shrink-0 text-foreground" })}
    >
      <Coins />
      Manage costs
      <ExternalLink />
      <span className="sr-only">(opens in a new tab)</span>
    </Link>
  );
}
