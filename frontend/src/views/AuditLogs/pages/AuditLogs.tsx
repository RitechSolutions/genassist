import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchAuditLogs, fetchUsers } from "@/services/auditLogs";
import { AuditLogCard } from "@/views/AuditLogs/components/AuditLogCard";
import { AuditLogDetailsDialog } from "@/views/AuditLogs/components/AuditLogDetailsDialog";
import { useIsMobile } from "@/hooks/useMobile";
import { Button } from "@/components/button";
import { ALL_FILTER_VALUE, FilterMenu, type FilterMenuGroup } from "@/components/FilterMenu";
import { format, startOfDay, subDays, endOfDay, addDays } from "date-fns";
import { DateRangePicker } from "@/components/date-range-picker";
import { usePersistedDateRange } from "@/hooks/usePersistedDateRange";
import { PageHeader } from "@/components/PageHeader";
import { Loader2, RefreshCcw } from "lucide-react";
import { User } from "@/interfaces/user.interface";
import { AuditLog } from "@/interfaces/audit-log.interface";

const AUDIT_ACTIONS = ["Insert", "Update", "Delete"];
const PAGE_SIZE = 30;

const getDefaultDateRange = () => {
  const today = new Date();
  return { from: startOfDay(subDays(today, 1)), to: endOfDay(addDays(today, 1)) };
};

export default function AuditLogs() {
  const isMobile = useIsMobile();
  const defaultRange = getDefaultDateRange();

  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedAuditLogId, setSelectedAuditLogId] = useState<string | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [dateRange, setDateRange] = usePersistedDateRange(defaultRange);
  const [selectedUser, setSelectedUser] = useState<string | null>(null);
  const [selectedAction, setSelectedAction] = useState<string | null>(null);
  const [tableName, setTableName] = useState<string>("");
  const [debouncedTableName, setDebouncedTableName] = useState<string>("");
  const [users, setUsers] = useState<User[]>([]);
  const sentinelRef = useRef<HTMLDivElement>(null);
  // Bumped on every reset so a response for superseded filters is dropped.
  const requestIdRef = useRef(0);

  useEffect(() => {
    const timeout = setTimeout(() => setDebouncedTableName(tableName.trim()), 1000);
    return () => clearTimeout(timeout);
  }, [tableName]);

  const dateFrom = dateRange?.from ? format(dateRange.from, "yyyy-MM-dd") : "";
  const dateTo = dateRange?.to ? format(dateRange.to, "yyyy-MM-dd") : "";

  const fetchPage = useCallback(
    (offset: number) =>
      fetchAuditLogs(
        dateFrom,
        dateTo,
        selectedAction || "",
        debouncedTableName,
        selectedUser ?? undefined,
        PAGE_SIZE,
        offset
      ),
    [dateFrom, dateTo, selectedAction, debouncedTableName, selectedUser]
  );

  /** Reloads from the first page — on mount, filter change, refresh and retry. */
  const reloadAuditLogs = useCallback(async () => {
    const requestId = ++requestIdRef.current;
    try {
      setIsRefreshing(true);
      setError(null);
      const logs = await fetchPage(0);
      if (requestId !== requestIdRef.current) return;
      setAuditLogs(logs);
      setHasMore(logs.length === PAGE_SIZE);
    } catch {
      if (requestId !== requestIdRef.current) return;
      setError("We couldn't load your audit logs. Please try again.");
    } finally {
      if (requestId === requestIdRef.current) setIsRefreshing(false);
    }
  }, [fetchPage]);

  const loadMore = useCallback(async () => {
    const requestId = requestIdRef.current;
    try {
      setIsLoadingMore(true);
      const logs = await fetchPage(auditLogs.length);
      if (requestId !== requestIdRef.current) return;
      setAuditLogs((prev) => [...prev, ...logs]);
      setHasMore(logs.length === PAGE_SIZE);
    } catch {
      // Stop auto-loading; Refresh starts over.
      if (requestId === requestIdRef.current) setHasMore(false);
    } finally {
      setIsLoadingMore(false);
    }
  }, [fetchPage, auditLogs.length]);

  useEffect(() => {
    reloadAuditLogs();
  }, [reloadAuditLogs]);

  // Infinite scroll: load the next page when the sentinel below the table comes into view.
  // Re-created after each load, so it keeps loading while the sentinel stays visible
  // (e.g. when the search hides most of the loaded rows).
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel || !hasMore || isRefreshing || isLoadingMore || error) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) loadMore();
      },
      { root: null, rootMargin: "200px", threshold: 0 }
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, isRefreshing, isLoadingMore, error, loadMore]);

  // The search box and the exact time range (the API filters by whole days) apply client-side.
  const visibleAuditLogs = useMemo(() => {
    const query = searchQuery.toLowerCase();
    return auditLogs.filter((log) => {
      const matchesSearchQuery =
        log.table_name.toLowerCase().includes(query) ||
        log.action_name.toLowerCase().includes(query);

      const logDate = new Date(log.modified_at);
      const isWithinDateRange =
        (!dateRange?.from || logDate >= dateRange.from) &&
        (!dateRange?.to || logDate <= dateRange.to);

      return matchesSearchQuery && isWithinDateRange;
    });
  }, [auditLogs, searchQuery, dateRange?.from, dateRange?.to]);

  useEffect(() => {
    const fetchUsersData = async () => {
      try {
        const fetchedUsers = await fetchUsers();
        setUsers(fetchedUsers);
      } catch (error) {
        // ignore
      }
    };
    fetchUsersData();
  }, []);

  const handleViewDetails = (logId: string) => {
    setSelectedAuditLogId(logId);
    setIsDialogOpen(true);
  };

  const filterGroups: FilterMenuGroup[] = [
    {
      key: "user",
      label: "User",
      allLabel: "All users",
      value: selectedUser ?? ALL_FILTER_VALUE,
      options: users.map((user) => ({ value: user.id, label: user.username })),
      onChange: (value) => {
        setSelectedUser(value === ALL_FILTER_VALUE ? null : value);
      },
    },
    {
      key: "action",
      label: "Action",
      allLabel: "All actions",
      value: selectedAction ?? ALL_FILTER_VALUE,
      options: AUDIT_ACTIONS.map((action) => ({ value: action, label: action })),
      onChange: (value) => {
        setSelectedAction(value === ALL_FILTER_VALUE ? null : value);
      },
    },
    {
      type: "text",
      key: "table",
      label: "Table name",
      placeholder: "e.g. users",
      value: tableName,
      onChange: (value) => {
        setTableName(value);
      },
    },
  ];

  return (
    <>
          <div className="flex-1 p-4 sm:p-6 lg:p-8">
            <div className="max-w-2xl xl:max-w-7xl mx-auto space-y-6">
              <PageHeader
                title="Audit Logs"
                subtitle="View system audit logs"
                searchQuery={searchQuery}
                onSearchChange={setSearchQuery}
                searchPlaceholder="Search audit logs..."
                filters={
                  <>
                    <DateRangePicker
                      value={dateRange}
                      onChange={setDateRange}
                      align="start"
                      placeholder="Select a date range"
                      triggerClassName="rounded-full w-full sm:w-auto"
                    />
                    <FilterMenu groups={filterGroups} align="end" className="h-10 text-sm max-md:w-full" />
                  </>
                }
                trailingActions={
                  <Button
                    variant="outline"
                    size="icon"
                    className="rounded-full shrink-0"
                    onClick={reloadAuditLogs}
                    disabled={isRefreshing}
                    aria-label="Refresh"
                    title="Refresh"
                  >
                    <RefreshCcw className={`w-4 h-4 ${isRefreshing ? "animate-spin" : ""}`} />
                  </Button>
                }
              />

              <AuditLogCard
                searchQuery={searchQuery}
                auditLogs={visibleAuditLogs}
                users={users}
                onViewDetails={handleViewDetails}
                loading={isRefreshing && auditLogs.length === 0}
                isRefreshing={isRefreshing && auditLogs.length > 0}
                error={error}
                onRetry={reloadAuditLogs}
              />

              <div ref={sentinelRef} aria-hidden className="h-px" />
              {isLoadingMore && (
                <div className="flex items-center justify-center gap-2 py-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading more…
                </div>
              )}
            </div>
          </div>

      <AuditLogDetailsDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        auditLogId={selectedAuditLogId}
        users={users}
      />
    </>
  );
}