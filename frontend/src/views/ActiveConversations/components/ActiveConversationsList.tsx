import { Button } from "@/components/button";
import { MessageSquare } from "lucide-react";
import type { NormalizedConversation } from "../helpers/activeConversations.types";
import { PageListSkeleton } from "@/components/skeletons";
import ConversationRow from "./ConversationRow";

interface ListProps {
  items: NormalizedConversation[];
  isLoading: boolean;
  error: Error | null;
  onRetry?: () => void;
  onClickRow?: (item: NormalizedConversation) => void;
  emptyPreviewText?: string;
}

export function ActiveConversationsList({ items, isLoading, error, onRetry, onClickRow }: ListProps) {
  if (error) {
    return (
      <div className="p-6 text-red-600 dark:text-red-400 flex items-center justify-between">
        <span>Failed to load conversations.</span>
        {onRetry && (
          <Button variant="outline" onClick={onRetry}>Retry</Button>
        )}
      </div>
    );
  }

  if (isLoading) {
    return <PageListSkeleton variant="conversation" rows={5} bordered={false} />;
  }

  if (!items || items.length === 0) {
    return (
      <div className="p-6 text-muted-foreground flex h-full items-center justify-center min-h-[200px] bg-muted">
        <div className="text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-background/70">
            <MessageSquare className="w-6 h-6 text-muted-foreground" />
          </div>
          <p className="text-sm font-medium text-foreground">No active conversations match your filters.</p>
          <p className="text-xs text-muted-foreground mt-1">Adjust sentiment or category to see more conversations.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full min-w-0">
      {items.map((item) => (
        <ConversationRow
          key={item.id}
          item={item}
          reason={item.effectiveSentiment === "negative" ? (item.negative_reason || "") : ""}
          onClick={onClickRow}
        />
      ))}
    </div>
  );
}

export default ActiveConversationsList;
