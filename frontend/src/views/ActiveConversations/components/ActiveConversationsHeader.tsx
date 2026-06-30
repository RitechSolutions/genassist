import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import { Link } from "react-router-dom";

interface HeaderProps {
  title: string;
}

export function ActiveConversationsHeader({ title }: HeaderProps) {
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3 sm:mb-6">
      <div className="flex min-w-0 items-center gap-2">
        <h2 className="text-lg font-semibold text-foreground">{title}</h2>
        <Badge className="bg-emerald-600 text-primary-foreground border-transparent px-2.5 py-0.5">
          Live
        </Badge>
      </div>
      <Link to="/transcripts?status=in_progress&status=takeover">
        <Button 
          variant="outline" 
          className="h-9 rounded-full border-input px-4 py-2 sm:h-10"
        >
          View all
        </Button>
      </Link>
    </div>
  );
}

export default ActiveConversationsHeader;