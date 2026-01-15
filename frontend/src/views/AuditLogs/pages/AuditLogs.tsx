import { useState, useEffect } from "react";
import { fetchAuditLogs, fetchUsers } from "@/services/auditLogs";
import { SidebarProvider, SidebarTrigger } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { AuditLogCard } from "@/views/AuditLogs/components/AuditLogCard";
import { AuditLogDetailsDialog } from "@/views/AuditLogs/components/AuditLogDetailsDialog";
import { useIsMobile } from "@/hooks/useMobile";
import { Search } from "lucide-react";
import { Button } from "@/components/button";
import { Select, SelectItem, SelectContent, SelectTrigger } from "@/components/select";
import { format, startOfDay, subDays, endOfDay } from "date-fns";
import { Calendar } from "@/components/calendar";
import { Popover, PopoverTrigger, PopoverContent } from "@/components/popover";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationPrevious,
  PaginationNext,
  PaginationEllipsis,
} from "@/components/pagination";
import { getPageList } from "@/helpers/pagination";

const getDefaultDateRange = () => {
  const today = new Date();
  return { from: startOfDay(subDays(today, 1)), to: endOfDay(today) };
};

export default function AuditLogs() {
  const isMobile = useIsMobile();
  const defaultRange = getDefaultDateRange();

  const [filteredAuditLogs, setFilteredAuditLogs] = useState([]);
  const [selectedAuditLogId, setSelectedAuditLogId] = useState<string | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [dateRange, setDateRange] = useState(defaultRange);
  const [selectedUser, setSelectedUser] = useState<string | null>(null);
  const [selectedAction, setSelectedAction] = useState<string | null>(null);
  const [users, setUsers] = useState<any[]>([]);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const pageSize = 30;

  const isLastPage = filteredAuditLogs.length < pageSize;
  const totalPages = currentPage + (isLastPage ? 0 : 1);
  const pageList = getPageList(currentPage, totalPages);

  const fetchFilteredAuditLogs = async () => {
    const date_from = dateRange.from ? format(dateRange.from, "yyyy-MM-dd") : "";
    const date_to = dateRange.to ? format(dateRange.to, "yyyy-MM-dd") : "";
    const action = selectedAction || "";
    const user = selectedUser ?? undefined;
    const offset = (currentPage - 1) * pageSize;


    try {
      const logs = await fetchAuditLogs(
        date_from,
        date_to,
        action,
        user, 
        pageSize,
        offset
      );
      const filtered = logs.filter((log) => {
        const matchesSearchQuery =
          log.table_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          log.action_name.toLowerCase().includes(searchQuery.toLowerCase());
  
        const matchesUser = selectedUser ? log.modified_by === selectedUser : true;
  
        const logDate = new Date(log.modified_at);
        const isWithinDateRange =
          (!dateRange.from || logDate >= dateRange.from) &&
          (!dateRange.to || logDate <= dateRange.to);
  
        return matchesSearchQuery && matchesUser && isWithinDateRange;
      });
      setFilteredAuditLogs(filtered);
    } catch (error) {
      // ignore
    }
  };

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

  useEffect(() => {
    fetchFilteredAuditLogs();
  }, [dateRange, selectedUser, selectedAction, currentPage]);

  const handleViewDetails = (logId: string) => {
    setSelectedAuditLogId(logId);
    setIsDialogOpen(true);
  };

  const handleClearFilters = () => {
    setSearchQuery("");
    setDateRange(defaultRange);
    setSelectedUser(null);
    setSelectedAction(null);
    setCurrentPage(1);
  };

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full">
        {!isMobile && <AppSidebar />}
        <main className="flex-1 flex flex-col bg-zinc-100 relative">
          <SidebarTrigger className="fixed top-4 z-10 h-8 w-8 bg-white/50 backdrop-blur-sm hover:bg-white/70 rounded-full shadow-md transition-[left] duration-200" />
          <div className="flex-1 p-8">
            <div className="max-w-2xl xl:max-w-7xl mx-auto space-y-6">
              <div className="flex justify-between items-start">
                <div>
                  <h1 className="text-3xl font-bold mb-2 animate-fade-down">Audit Logs</h1>
                  <p className="text-muted-foreground animate-fade-up">View system audit logs</p>
                </div>
              </div>

              <div className="flex flex-col lg:flex-row justify-between gap-y-4 lg:gap-y-0 gap-x-4">
                <div className="inline-flex gap-4">
                  <Popover>
                    <PopoverTrigger asChild>
                      <button className="border px-4 py-2 rounded text-sm bg-white shadow-sm hover:bg-gray-50">
                        {dateRange.from && dateRange.to
                          ? `${format(dateRange.from, "PPP")} - ${format(dateRange.to, "PPP")}`
                          : "Select a date range"}
                      </button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0" align="start">
                      <Calendar
                        mode="range"
                        selected={dateRange}
                        onSelect={(range) => setDateRange({ from: range?.from, to: range?.to })}
                        numberOfMonths={1}
                      />
                    </PopoverContent>
                  </Popover>

                  <div className="w-40">
                    <Select value={selectedUser ?? ""} onValueChange={(value) => setSelectedUser(value === "" ? null : value)}>
                      <SelectTrigger className="w-full h-full text-sm border rounded-md px-4 py-2 bg-white focus:ring-0 focus:ring-offset-0">
                        {selectedUser ? users.find((u) => u.id === selectedUser)?.username : "Select User"}
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value={null}>All Users</SelectItem>
                        {users.map((user) => (
                          <SelectItem key={user.id} value={user.id}>{user.username}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="w-40">
                    <Select value={selectedAction ?? undefined} onValueChange={(value) => setSelectedAction(value || null)}>
                      <SelectTrigger className="w-full h-full text-sm border rounded-md px-4 py-2 bg-white focus:ring-0 focus:ring-offset-0">
                        {selectedAction ? selectedAction : "Select Action"}
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value={null}>All Actions</SelectItem>
                        <SelectItem value="Insert">Insert</SelectItem>
                        <SelectItem value="Update">Update</SelectItem>
                        <SelectItem value="Delete">Delete</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="relative flex gap-x-4">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                  <input
                    type="text"
                    placeholder="Search audit logs..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-10 pr-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                  <div className="flex justify-center items-center">
                    <Button onClick={handleClearFilters}>Clear</Button>
                  </div>
                </div>
              </div>

              <AuditLogCard
                searchQuery={searchQuery}
                auditLogs={filteredAuditLogs}
                users={users}
                selectedUser={selectedUser}
                onViewDetails={handleViewDetails}
              />

              <Pagination>
              <PaginationContent>
                <PaginationItem>
                  <PaginationPrevious
                  onClick={() => {
                    if (currentPage <= 1) return;
                    setCurrentPage((p) => Math.max(1, p - 1));
                    }}
                    aria-disabled={currentPage <= 1}
                    className={currentPage <= 1 
                      ? "opacity-50 cursor-not-allowed"
                      : "cursor-pointer"}
                  />
                </PaginationItem>

                {pageList.map((pageNumber, idx) => (
                  <PaginationItem key={idx}>
                    {typeof pageNumber === "number" ? (
                      <PaginationLink
                        onClick={() => {
                          if (pageNumber === currentPage) return;
                          setCurrentPage(pageNumber);
                        }}
                        isActive={pageNumber === currentPage}
                        href="#"
                        className="rounded-xl"
                      >
                        {pageNumber}
                      </PaginationLink>
                    ) : (
                      <PaginationEllipsis />
                    )}
                  </PaginationItem>
                ))}

                <PaginationItem>
                  <PaginationNext
                    onClick={() => {
                      if (filteredAuditLogs.length < pageSize) return;
                      setCurrentPage((p) => p + 1);
                        }}
                        aria-disabled={filteredAuditLogs.length < pageSize}
                        className={filteredAuditLogs.length < pageSize 
                          ? "opacity-50 cursor-not-allowed"
                          : "cursor-pointer"}
                  />
                </PaginationItem>
              </PaginationContent>
            </Pagination>


            </div>
          </div>
        </main>
      </div>

      <AuditLogDetailsDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        auditLogId={selectedAuditLogId}
        users={users}
      />
    </SidebarProvider>
  );
}