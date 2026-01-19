import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import { Link } from "react-router-dom";

interface HeaderProps {
  title: string;
}

export function ActiveConversationsHeader({ title }: HeaderProps) {
  return (
    <div className="flex items-center justify-between gap-3 mb-6">
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-semibold text-foreground">{title}</h2>
        <Badge className="bg-emerald-600 text-primary-foreground border-transparent px-2.5 py-0.5">
          Live
        </Badge>
      </div>
      <Link to="/transcripts?status=in_progress&status=takeover">
        <Button 
          variant="outline" 
          className="h-10 px-4 py-2 rounded-full border-input"
        >
          View all
        </Button>
      </Link>
    </div>
  );
}

export default ActiveConversationsHeader;