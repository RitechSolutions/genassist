import { useCallback, useRef, useState, useEffect } from "react";
import { Card } from "@/components/card";
import { ThumbsUp, Clock, Star, Users } from "lucide-react";
import { OperatorDetailsDialog } from "./OperatorDetailsDialog";
import { useSearchParams } from "react-router-dom";
import { fetchOperatorById, fetchOperatorsPaginated } from "@/services/operators";
import { Operator, OperatorListItem } from "@/interfaces/operator.interface";
import { formatExactDuration } from "@/helpers/formatters";
import { Button } from "@/components/button";
import { PageListSkeleton } from "@/components/skeletons";
import { ListEmptyState } from "@/components/ListEmptyState";
import { ListErrorState } from "@/components/ListErrorState";
import { PaginationBar } from "@/components/PaginationBar";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";

const PAGE_SIZE = 20;
const SEARCH_DEBOUNCE_MS = 300;

const formatConversationCount = (count: number) =>
  `${count} ${count === 1 ? "conversation" : "conversations"}`;

interface OperatorsCardProps {
  searchQuery: string;
  refreshKey: number;
  onCreate?: () => void;
}

export function OperatorsCard({
  searchQuery,
  refreshKey,
  onCreate,
}: OperatorsCardProps) {
  const [operators, setOperators] = useState<OperatorListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<Operator | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  // Keyed by operator id, not row index, so ids can't collide across pages.
  const [imageErrors, setImageErrors] = useState(new Set<string>());

  const [searchParams, setSearchParams] = useSearchParams();
  const operatorParam = searchParams.get("operator");
  const page = Math.max(1, parseInt(searchParams.get("page") || "1", 10) || 1);
  const debouncedSearch = useDebouncedValue(searchQuery, SEARCH_DEBOUNCE_MS).trim();

  const requestSeqRef = useRef(0);
  const lastResetSigRef = useRef(`${debouncedSearch}|${refreshKey}`);

  // Functional updater so the page edit always applies to the current params
  // rather than a value captured at render time.
  const goToPage = useCallback(
    (next: number) => {
      setSearchParams(
        (prev) => {
          const params = new URLSearchParams(prev);
          if (next <= 1) params.delete("page");
          else params.set("page", String(next));
          return params;
        },
        { replace: true }
      );
    },
    [setSearchParams]
  );

  const goToPageRef = useRef(goToPage);
  useEffect(() => {
    goToPageRef.current = goToPage;
  });

  const handleModalOpenChange = (open: boolean) => {
    setIsModalOpen(open);
    if (!open && operatorParam) {
      setSearchParams(
        (prev) => {
          const params = new URLSearchParams(prev);
          params.delete("operator");
          return params;
        },
        { replace: true }
      );
    }
  };

  const loadOperators = useCallback(async () => {
    const seq = ++requestSeqRef.current;

    const resetSig = `${debouncedSearch}|${refreshKey}`;
    if (resetSig !== lastResetSigRef.current) {
      lastResetSigRef.current = resetSig;
      // A new search or a freshly created operator belongs on page 1.
      if (page !== 1) {
        goToPageRef.current(1);
        return;
      }
    }

    setLoading(true);
    setError(null);
    try {
      const data = await fetchOperatorsPaginated(page, PAGE_SIZE, debouncedSearch);
      if (seq !== requestSeqRef.current) return;

      // A stale ?page= past the end: fall back to the last page.
      if (data.total > 0 && data.items.length === 0 && page > data.total_pages) {
        goToPageRef.current(data.total_pages);
        return;
      }

      setOperators(data.items);
      setTotal(data.total);
    } catch (err) {
      if (seq !== requestSeqRef.current) return;
      console.error("Failed to load operators:", err);
      setError("We couldn't load your operators. Please try again.");
    } finally {
      if (seq === requestSeqRef.current) setLoading(false);
    }
  }, [page, debouncedSearch, refreshKey]);

  useEffect(() => {
    loadOperators();
  }, [loadOperators]);

  // Open the profile dialog for ?operator=<id>, fetching it when the id isn't
  // on the current page.
  useEffect(() => {
    if (!operatorParam) return;

    const match = operators.find((op) => op.id === operatorParam);
    if (match) {
      setSelectedAgent(match);
      setIsModalOpen(true);
      return;
    }
    if (loading) return;

    let cancelled = false;
    const requestedId = operatorParam;
    fetchOperatorById(requestedId)
      .then((operator) => {
        if (cancelled || operator?.id !== requestedId) return;
        setSelectedAgent(operator);
        setIsModalOpen(true);
      })
      .catch(() => {
        // Invalid or unavailable operator deep links remain a silent no-op.
      });

    return () => {
      cancelled = true;
    };
  }, [operatorParam, operators, loading]);

  function getInitials(firstName = "", lastName = "") {
    return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
  }

  const handleImageError = (operatorId: string) => {
    setImageErrors((prevErrors) => new Set(prevErrors).add(operatorId));
  };

  const isSearchActive = debouncedSearch !== "";

  return (
    <>
      <Card className="p-4 shadow-sm animate-fade-up bg-card dark:bg-zinc-900">
        <div className="space-y-2">
          {loading ? (
            <PageListSkeleton variant="operator" rows={5} bordered={false} />
          ) : error ? (
            <ListErrorState message={error} onRetry={loadOperators} />
          ) : operators.length > 0 ? (
            operators.map((agent) => (
              <div
                key={agent.id}
                className="flex items-center gap-3 p-2 rounded-lg transition-colors hover:bg-muted/30 cursor-pointer"
                onClick={() => {
                  setSelectedAgent(agent);
                  setIsModalOpen(true);
                }}
              >
                {!imageErrors.has(agent.id) && agent.avatar ? (
                  <img
                    src={agent.avatar}
                    alt={`${agent.firstName} ${agent.lastName}`}
                    className="w-10 h-10 rounded-full object-cover shrink-0"
                    onError={() => handleImageError(agent.id)}
                  />
                ) : (
                  <div className="w-10 h-10 flex items-center justify-center rounded-full bg-muted text-muted-foreground text-sm font-semibold shrink-0">
                    {getInitials(agent.firstName, agent.lastName)}
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-semibold text-accent-foreground truncate">
                    {agent.firstName} {agent.lastName}
                  </h3>
                  <div className="flex items-center gap-3 mt-1 flex-wrap">
                    <div className="flex items-center gap-1">
                      <ThumbsUp className="w-3.5 h-3.5 text-muted-foreground" />
                      <span className="text-xs text-muted-foreground">
                        {agent.operator_statistics?.positive ?? 0}%
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                      <span className="text-xs text-muted-foreground">
                        {formatExactDuration(
                          agent.operator_statistics?.totalCallDuration
                        )}
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Star className="w-3.5 h-3.5 text-yellow-400" />
                      <span className="text-xs text-muted-foreground">
                        {agent.operator_statistics?.score ?? 0}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="text-xs font-medium text-muted-foreground shrink-0">
                  {formatConversationCount(agent.operator_statistics?.callCount ?? 0)}
                </div>
              </div>
            ))
          ) : (
            <ListEmptyState
              icon={<Users className="h-12 w-12 text-muted-foreground" />}
              title={
                isSearchActive ? "No matching operators" : "No operators yet"
              }
              description={
                isSearchActive
                  ? "No operators match your search. Try a different name."
                  : "Operators are the people who handle escalated conversations. They'll appear here once they're added."
              }
              action={
                !isSearchActive && onCreate ? (
                  <Button className="rounded-full" onClick={onCreate}>
                    Create your first operator
                  </Button>
                ) : undefined
              }
            />
          )}
        </div>

        {!loading && !error && (
          <PaginationBar
            total={total}
            currentPage={page}
            pageSize={PAGE_SIZE}
            pageItemCount={operators.length}
            onPageChange={goToPage}
          />
        )}
      </Card>

      <OperatorDetailsDialog
        operator={selectedAgent}
        isOpen={isModalOpen}
        onOpenChange={handleModalOpenChange}
      />
    </>
  );
}
