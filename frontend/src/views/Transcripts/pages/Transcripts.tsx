import { SidebarProvider, SidebarTrigger } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import {
  MessageSquare,
  PlayCircle,
  CheckCircle,
  MinusCircle,
  AlertCircle,
  Radio,
  ThumbsUp,
  ThumbsDown,
  Upload,
  ChevronDown,
  RefreshCw,
  SmileIcon,
  Award,
  Zap,
  SlidersHorizontal,
} from "lucide-react";
import { Card } from "@/components/card";
import { Button } from "@/components/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/tabs";
import { useIsMobile } from "@/hooks/useMobile";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/dropdown-menu";
import { type CSSProperties, useState, useEffect, useMemo, type ReactNode } from "react";
import { Transcript } from "@/interfaces/transcript.interface";
import { TranscriptDialog } from "../components/TranscriptDialog";
import { ActiveConversationDialog } from "@/views/ActiveConversations/components/ActiveConversationDialog";
import { useTranscriptData } from "../hooks/useTranscriptData";
import { formatDuration, getEffectiveSentiment, HOSTILITY_POSITIVE_MAX, HOSTILITY_NEUTRAL_MAX } from "../helpers/formatting";
import { Badge } from "@/components/badge";
import { useLocation, useNavigate } from "react-router-dom";
import { useToast } from "@/hooks/useToast";
import { conversationService } from "@/services/liveConversations";
import { transformTranscript } from "../helpers/transformers";
import { UploadMediaDialog } from "@/views/MediaUpload";
import { getPaginationMeta } from "@/helpers/pagination";
import { PaginationBar } from "@/components/PaginationBar";
import { SearchInput } from "@/components/SearchInput";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/RadixTooltip";
import { useAgentsList } from "@/views/Analytics/hooks/useAgentsList";
import { DateRangePicker } from "@/components/date-range-picker";
import type { DateRange } from "react-day-picker";
import { format, subDays } from "date-fns";
import { Switch } from "@/components/switch";
import { Label } from "@/components/label";

const ITEMS_PER_PAGE = 10;

type QualityFilterKey = "customer_satisfaction" | "quality_of_service" | "resolution_rate" | "efficiency";
type QualityLevel = "all" | "low" | "medium" | "high";

interface QualityFilterState {
  customer_satisfaction: QualityLevel;
  quality_of_service: QualityLevel;
  resolution_rate: QualityLevel;
  efficiency: QualityLevel;
}

const QUALITY_RANGES: Record<QualityLevel, { min?: number; max?: number }> = {
  all: {},
  low: { min: 0, max: 3 },
  medium: { min: 4, max: 6 },
  high: { min: 7, max: 10 },
};

// Icons & colors aligned with AnalyticsMetricsSection
const QUALITY_METRICS: { key: QualityFilterKey; label: string; shortLabel: string; icon: ReactNode; color: string }[] = [
  { key: "customer_satisfaction", label: "Customer Satisfaction", shortLabel: "Satisfaction", icon: <SmileIcon className="h-3.5 w-3.5" style={{ color: "#10b981" }} />, color: "#10b981" },
  { key: "quality_of_service", label: "Quality of Service", shortLabel: "Quality", icon: <Award className="h-3.5 w-3.5" style={{ color: "#8b5cf6" }} />, color: "#8b5cf6" },
  { key: "resolution_rate", label: "Resolution Rate", shortLabel: "Resolution", icon: <CheckCircle className="h-3.5 w-3.5" style={{ color: "#f59e0b" }} />, color: "#f59e0b" },
  { key: "efficiency", label: "Efficiency", shortLabel: "Efficiency", icon: <Zap className="h-3.5 w-3.5" style={{ color: "#06b6d4" }} />, color: "#06b6d4" },
];

type StatusFilter = "all" | "live" | "finalized";

const formatScorePercentage = (value: number) =>
  value > 0 ? `${Math.round((value / 10) * 100)}%` : "—";

const getScoreBadgeStyle = (color: string): CSSProperties => ({
  backgroundColor: `${color}15`,
  borderColor: `${color}30`,
  color,
});

const SENTIMENT_CONFIG: Record<string, { icon: ReactNode; bg: string; text: string; border: string }> = {
  positive: { icon: <CheckCircle className="w-3 h-3" />, bg: "bg-emerald-50", text: "text-emerald-700", border: "border-emerald-200" },
  neutral: { icon: <MinusCircle className="w-3 h-3" />, bg: "bg-amber-50", text: "text-amber-700", border: "border-amber-200" },
  negative: { icon: <AlertCircle className="w-3 h-3" />, bg: "bg-rose-50", text: "text-rose-600", border: "border-rose-200" },
  "very-bad": { icon: <AlertCircle className="w-3 h-3" />, bg: "bg-rose-50", text: "text-rose-600", border: "border-rose-200" },
};
const DEFAULT_SENTIMENT = { icon: <MinusCircle className="w-3 h-3" />, bg: "bg-gray-50", text: "text-gray-600", border: "border-gray-200" };

const Transcripts = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { toast } = useToast();
  const searchParams = new URLSearchParams(location.search);
  const { agents } = useAgentsList();

  const [selectedTranscript, setSelectedTranscript] = useState<Transcript | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isLiveTranscriptSelected, setIsLiveTranscriptSelected] = useState(false);
  const [activeTab, setActiveTab] = useState(searchParams.get("sentiment") || "all");
  const [supportType, setSupportType] = useState(searchParams.get("type") || "all");
  const [searchQuery, setSearchQuery] = useState(searchParams.get("query") || "");
  const [currentPage, setCurrentPage] = useState(
    Math.max(1, parseInt(searchParams.get("page") || "1", 10) || 1)
  );
  const [isUploadDialogOpen, setIsUploadDialogOpen] = useState(false);
  const [orderBy, setOrderBy] = useState("");
  const [sortDirection, setSortDirection] = useState("desc");
  const [selectedAgentId, setSelectedAgentId] = useState(searchParams.get("agent_id") || "all");
  const [hideEmpty, setHideEmpty] = useState(true);
  const [qualityFilters, setQualityFilters] = useState<QualityFilterState>({
    customer_satisfaction: "all",
    quality_of_service: "all",
    resolution_rate: "all",
    efficiency: "all",
  });

  // Derive initial status filter from URL
  const initStatusFilter = (): StatusFilter => {
    const statuses = searchParams.getAll("status");
    if (statuses.includes("finalized")) return "finalized";
    if (statuses.includes("in_progress") && statuses.includes("takeover")) return "live";
    return "all";
  };
  const [statusFilter, setStatusFilter] = useState<StatusFilter>(initStatusFilter);
  const [dateRange, setDateRange] = useState<DateRange | undefined>({
    from: subDays(new Date(), 7),
    to: new Date(),
  });

  // Calculate hostility parameters based on sentiment
  const getHostilityParams = (sentiment: string) => {
    return {
      hostility_positive_max: HOSTILITY_POSITIVE_MAX,
      hostility_neutral_max: HOSTILITY_NEUTRAL_MAX
    };
  };

  const hostilityParams = getHostilityParams(activeTab);

  // Build conversation_status from statusFilter
  const conversationStatus = useMemo(() => {
    if (statusFilter === "live") return ["in_progress", "takeover"];
    if (statusFilter === "finalized") return ["finalized"];
    return undefined;
  }, [statusFilter]);

  // Build score filters from quality filter state
  const scoreFilters = useMemo(() => {
    const filters: Record<string, number | undefined> = {};
    for (const metric of QUALITY_METRICS) {
      const level = qualityFilters[metric.key];
      const range = QUALITY_RANGES[level];
      if (range.min !== undefined) filters[`${metric.key}_min`] = range.min;
      if (range.max !== undefined) filters[`${metric.key}_max`] = range.max;
    }
    return Object.keys(filters).length > 0 ? filters : undefined;
  }, [qualityFilters]);

  const activeQualityCount = useMemo(
    () => Object.values(qualityFilters).filter((v) => v !== "all").length,
    [qualityFilters]
  );

  const { data, total, loading, error, refetch } = useTranscriptData({
    limit: ITEMS_PER_PAGE,
    skip: (currentPage - 1) * ITEMS_PER_PAGE,
    sentiment: activeTab,
    hostility_positive_max: hostilityParams.hostility_positive_max,
    hostility_neutral_max: hostilityParams.hostility_neutral_max,
    conversation_status: conversationStatus,
    order_by: orderBy || undefined,
    sort_direction: orderBy ? sortDirection : undefined,
    agent_id: selectedAgentId !== "all" ? selectedAgentId : undefined,
    scoreFilters,
    from_date: dateRange?.from ? format(dateRange.from, "yyyy-MM-dd") : undefined,
    to_date: dateRange?.to ? format(dateRange.to, "yyyy-MM-dd") : undefined,
    exclude_empty: hideEmpty || undefined,
  });

  const isMobile = useIsMobile();
  const transcripts = Array.isArray(data) ? data : [];
  const totalCount = typeof total === "number" ? total : transcripts.length;

  const updateUrlParams = (params: Record<string, string | number | string[] | null>) => {
    const newSearchParams = new URLSearchParams(location.search);

    Object.entries(params).forEach(([key, value]) => {
      if (value === null || value === undefined || value === "") {
        newSearchParams.delete(key);
      } else if (Array.isArray(value)) {
        newSearchParams.delete(key);
        value.forEach(v => {
          if (v) newSearchParams.append(key, v);
        });
      } else {
        newSearchParams.set(key, value.toString());
      }
    });

    navigate({ search: newSearchParams.toString() }, { replace: true });
  };

  const handleStatusFilterChange = (value: string) => {
    const v = value as StatusFilter;
    setStatusFilter(v);
    setCurrentPage(1);
    if (v === "live") {
      updateUrlParams({ status: ["in_progress", "takeover"], page: 1 });
    } else if (v === "finalized") {
      updateUrlParams({ status: ["finalized"], page: 1 });
    } else {
      updateUrlParams({ status: null, page: 1 });
    }
  };

  const isLiveTranscript = (transcript: Transcript) => {
    return transcript?.status === "in_progress" || transcript?.status === "takeover";
  };

  const isCallTranscript = (transcript: Transcript) => {
    return Boolean(transcript?.recording_id) || Boolean(transcript?.metadata?.isCall);
  };

  useEffect(() => {
    const params = new URLSearchParams(location.search);

    // Update filter states based on URL
    setActiveTab(params.get("sentiment") || "all");
    setSupportType(params.get("type") || "all");
    setSearchQuery(params.get("query") || "");
    setCurrentPage(
      Math.max(1, parseInt(params.get("page") || "1", 10) || 1)
    );
    setSelectedAgentId(params.get("agent_id") || "all");

    const statusValues = params.getAll("status");
    if (statusValues.includes("finalized")) {
      setStatusFilter("finalized");
    } else if (statusValues.includes("in_progress") && statusValues.includes("takeover")) {
      setStatusFilter("live");
    } else {
      setStatusFilter("all");
    }
  }, [location.search]);

  // Fetch latest conversation data when opening the dialog
  useEffect(() => {
    if (!isModalOpen || !selectedTranscript?.id) return;

    let cancelled = false;
    const conversationId = selectedTranscript.id;

    const refreshConversation = async () => {
      try {
        const backend = await conversationService.fetchConversationsTranscriptsAndData(conversationId);
        if (cancelled) return;
        setSelectedTranscript(transformTranscript(backend));
      } catch {
        if (!cancelled) {
          toast({
            title: "Could not refresh",
            description: "Failed to load latest conversation data.",
            variant: "destructive",
          });
        }
      }
    };

    refreshConversation();
    return () => {
      cancelled = true;
    };
  }, [isModalOpen, selectedTranscript?.id]);

  // Handle filter changes
  const handleSentimentChange = (value: string) => {
    setActiveTab(value);
    setCurrentPage(1);

    const hostilityParams = getHostilityParams(value);
    updateUrlParams({
      sentiment: value === "all" ? null : value,
      page: 1,
      hostility_positive_max: hostilityParams.hostility_positive_max,
      hostility_neutral_max: hostilityParams.hostility_neutral_max
    });
  };

  const handleSupportTypeChange = (value: string) => {
    setSupportType(value);
    updateUrlParams({ type: value === "all" ? null : value, page: 1 });
  };

  const handleAgentChange = (value: string) => {
    setSelectedAgentId(value);
    setCurrentPage(1);
    updateUrlParams({ agent_id: value === "all" ? null : value, page: 1 });
  };

  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    updateUrlParams({ query: value || null, page: 1 });
  };

  const handlePageChange = (newPage: number) => {
    const nextPage = Math.max(1, newPage);
    setCurrentPage(nextPage);
    updateUrlParams({ page: nextPage === 1 ? null : nextPage });
  };

  const applySort = (by: string, dir: string) => {
    setOrderBy(by);
    setSortDirection(dir);
    setCurrentPage(1);
    updateUrlParams({ page: 1 });
  };

  const handleQualityFilter = (key: QualityFilterKey, level: QualityLevel) => {
    setQualityFilters((prev) => ({ ...prev, [key]: level }));
    setCurrentPage(1);
    updateUrlParams({ page: 1 });
  };

  const handleDateRangeChange = (value: DateRange | undefined) => {
    setDateRange(value);
    setCurrentPage(1);
    updateUrlParams({ page: 1 });
  };

  const getSortLabel = (): { label: string; icon: ReactNode } | null => {
    if (!orderBy) return null;
    const dirLabel = sortDirection === "desc" ? "High\u2192Low" : "Low\u2192High";
    const sortMap: Record<string, { label: string; icon: ReactNode }> = {
      thumbs_down_count: { label: `Thumbs Down \u00b7 ${dirLabel}`, icon: <ThumbsDown className="h-4 w-4 text-red-600 shrink-0" /> },
      thumbs_up_count: { label: `Thumbs Up \u00b7 ${dirLabel}`, icon: <ThumbsUp className="h-4 w-4 text-green-600 shrink-0" /> },
      customer_satisfaction: { label: `Satisfaction \u00b7 ${dirLabel}`, icon: <SmileIcon className="h-4 w-4 shrink-0" style={{ color: "#10b981" }} /> },
      quality_of_service: { label: `Quality \u00b7 ${dirLabel}`, icon: <Award className="h-4 w-4 shrink-0" style={{ color: "#8b5cf6" }} /> },
      resolution_rate: { label: `Resolution \u00b7 ${dirLabel}`, icon: <CheckCircle className="h-4 w-4 shrink-0" style={{ color: "#f59e0b" }} /> },
      efficiency: { label: `Efficiency \u00b7 ${dirLabel}`, icon: <Zap className="h-4 w-4 shrink-0" style={{ color: "#06b6d4" }} /> },
    };
    return sortMap[orderBy] ?? null;
  };

  const activeSort = getSortLabel();

  const handleRefreshConversations = () => {
    refetch();
    toast({
      title: "Refreshing",
      description: "Conversations are being refreshed.",
    });
  };

  const filteredTranscripts = transcripts.filter((transcript) => {
    const title = transcript?.metadata?.title?.toLowerCase() || "";
    const topic = transcript?.metadata?.topic?.toLowerCase() || "";
    const searchLower = searchQuery.toLowerCase().trim();

    const matchesSearch =
      searchQuery.trim() === "" ||
      title.includes(searchLower) ||
      topic.includes(searchLower);

    const matchesSupportType =
      supportType === "all" || topic.includes(supportType.toLowerCase());

    return matchesSearch && matchesSupportType;
  });

  const pagination = getPaginationMeta(
    totalCount,
    ITEMS_PER_PAGE,
    currentPage
  );
  const paginatedTranscripts = filteredTranscripts;
  const pageItemCount = paginatedTranscripts.length;

  const handleTakeOver = async (transcriptId: string): Promise<boolean> => {
    try {
      const success = await conversationService.takeoverConversation(transcriptId);
      if (success) {
        toast({
          title: "Success",
          description: "Successfully took over the conversation",
        });
        refetch();
        if (selectedTranscript && selectedTranscript.id === transcriptId) {
          setSelectedTranscript(prev => prev ? { ...prev, status: "takeover" } : null);
        }
      }
      return success;
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to take over conversation",
        variant: "destructive",
      });
      return false;
    }
  };

  const getQualityScores = (transcript: Transcript) => {
    const m = transcript.metrics;
    if (!m) return null;
    const scores = [
      { ...QUALITY_METRICS[0], value: m.customerSatisfaction },
      { ...QUALITY_METRICS[1], value: m.serviceQuality },
      { ...QUALITY_METRICS[2], value: m.resolutionRate },
      { ...QUALITY_METRICS[3], value: m.efficiency },
    ];
    // Only show if at least one score is > 0 (i.e. analysis exists)
    if (scores.every((s) => s.value === 0)) return null;
    return scores;
  };

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full overflow-x-hidden">
        {!isMobile && <AppSidebar />}
        <main className="flex-1 flex flex-col bg-zinc-100 min-w-0 relative peer-data-[state=expanded]:md:ml-[calc(var(--sidebar-width)-2px)] peer-data-[state=collapsed]:md:ml-0 transition-[margin] duration-200">
          <SidebarTrigger className="fixed top-4 z-10 h-8 w-8 bg-white/50 backdrop-blur-sm hover:bg-white/70 rounded-full shadow-md transition-[left] duration-200" />
          <div className="flex-1 p-4 sm:p-6 lg:p-8">
            <div className="max-w-7xl mx-auto space-y-4 w-full">
              {/* Top row: Title/Upload | Agent, Date Range, Search */}
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between sm:flex-wrap">
                <div className="min-w-0">
                  <div className="flex items-center gap-3">
                    <h1 className="text-2xl md:text-3xl font-bold mb-1 animate-fade-down">
                      Conversations
                    </h1>
                    <Button
                      onClick={() => setIsUploadDialogOpen(true)}
                      variant="outline"
                      size="sm"
                    >
                      <Upload className="w-4 h-4" />
                      Upload
                    </Button>
                  </div>
                  <p className="text-sm md:text-base text-muted-foreground animate-fade-up">
                    Review and analyze your conversation transcripts
                  </p>
                </div>
                <div className="flex flex-col sm:flex-row gap-2 sm:gap-4 w-full sm:w-auto">
                  <Select value={selectedAgentId} onValueChange={handleAgentChange}>
                    <SelectTrigger className="w-full sm:w-[180px] bg-white">
                      <SelectValue placeholder="All Agents" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Agents</SelectItem>
                      {agents.map((agent) => (
                        <SelectItem key={agent.id} value={agent.id}>
                          {agent.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <DateRangePicker value={dateRange} onChange={handleDateRangeChange} />
                  <SearchInput
                    value={searchQuery}
                    onChange={handleSearchChange}
                    placeholder="Search conversations..."
                  />
                </div>
              </div>

              {/* Filter bar */}
              <div className="w-full flex flex-wrap items-center gap-2 rounded-full bg-white border border-gray-100 px-3 py-1.5 shadow-sm">
                <Tabs
                  value={activeTab}
                  className="min-w-0"
                  onValueChange={handleSentimentChange}
                >
                  <TabsList className="flex-wrap justify-start gap-1">
                    <TabsTrigger value="all" className="flex items-center gap-1.5 text-xs">
                      <CheckCircle className="w-3.5 h-3.5" />
                      All
                    </TabsTrigger>
                    <TabsTrigger value="positive" className="flex items-center gap-1.5 text-xs">
                      <CheckCircle className="w-3.5 h-3.5 text-green-500" />
                      Positive
                    </TabsTrigger>
                    <TabsTrigger value="neutral" className="flex items-center gap-1.5 text-xs">
                      <MinusCircle className="w-3.5 h-3.5 text-yellow-500" />
                      Neutral
                    </TabsTrigger>
                    <TabsTrigger value="negative" className="flex items-center gap-1.5 text-xs">
                      <AlertCircle className="w-3.5 h-3.5 text-orange-400" />
                      Bad
                    </TabsTrigger>
                  </TabsList>
                </Tabs>

                <div className="flex items-center gap-1.5 shrink-0 flex-wrap ml-auto">
                  <Select value={statusFilter} onValueChange={handleStatusFilterChange}>
                    <SelectTrigger className="w-[120px] bg-white h-8 rounded-full text-xs">
                      <SelectValue placeholder="Status" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Status</SelectItem>
                      <SelectItem value="live">
                        <span className="flex items-center gap-1.5">
                          <Radio className="w-3 h-3 text-green-500" />
                          Live
                        </span>
                      </SelectItem>
                      <SelectItem value="finalized">
                        <span className="flex items-center gap-1.5">
                          <CheckCircle className="w-3 h-3 text-blue-500" />
                          Finalized
                        </span>
                      </SelectItem>
                    </SelectContent>
                  </Select>
                  <Select value={supportType} onValueChange={handleSupportTypeChange}>
                    <SelectTrigger className="w-[130px] bg-white h-8 rounded-full text-xs">
                      <SelectValue placeholder="Support Type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Types</SelectItem>
                      <SelectItem value="Product Inquiry">Product Inquiry</SelectItem>
                      <SelectItem value="Technical Support">Technical Support</SelectItem>
                      <SelectItem value="Billing Question">Billing Questions</SelectItem>
                      <SelectItem value="Other">Other</SelectItem>
                    </SelectContent>
                  </Select>
                  {/* Quality filter dropdown */}
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button
                        type="button"
                        className={`flex h-8 shrink-0 items-center gap-1.5 rounded-full border px-2.5 text-xs ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1 transition-colors ${
                          activeQualityCount > 0
                            ? "border-primary/30 bg-primary/5 text-foreground"
                            : "border-input bg-white text-muted-foreground hover:bg-gray-50"
                        }`}
                      >
                        <SlidersHorizontal className="h-3.5 w-3.5 shrink-0" />
                        <span>Quality</span>
                        {activeQualityCount > 0 && (
                          <span className="flex h-4 min-w-[16px] items-center justify-center rounded-full bg-primary px-1 text-[10px] font-medium text-primary-foreground">
                            {activeQualityCount}
                          </span>
                        )}
                        <ChevronDown className="h-3 w-3 shrink-0 opacity-50" />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="min-w-[12rem]">
                      {activeQualityCount > 0 && (
                        <DropdownMenuItem
                          onClick={() => {
                            setQualityFilters({
                              customer_satisfaction: "all",
                              quality_of_service: "all",
                              resolution_rate: "all",
                              efficiency: "all",
                            });
                            setCurrentPage(1);
                            updateUrlParams({ page: 1 });
                          }}
                          className="text-muted-foreground"
                        >
                          Clear quality filters
                        </DropdownMenuItem>
                      )}
                      {QUALITY_METRICS.map((metric) => (
                        <DropdownMenuSub key={metric.key}>
                          <DropdownMenuSubTrigger className="flex items-center gap-2">
                            {metric.icon}
                            {metric.label}
                            {qualityFilters[metric.key] !== "all" && (
                              <Badge variant="outline" className="ml-auto text-[10px] px-1 py-0">
                                {qualityFilters[metric.key]}
                              </Badge>
                            )}
                          </DropdownMenuSubTrigger>
                          <DropdownMenuSubContent>
                            <DropdownMenuItem onClick={() => handleQualityFilter(metric.key, "all")}>
                              All {qualityFilters[metric.key] === "all" && "\u2713"}
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleQualityFilter(metric.key, "low")}>
                              Low (0-30%) {qualityFilters[metric.key] === "low" && "\u2713"}
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleQualityFilter(metric.key, "medium")}>
                              Medium (40-60%) {qualityFilters[metric.key] === "medium" && "\u2713"}
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleQualityFilter(metric.key, "high")}>
                              High (70-100%) {qualityFilters[metric.key] === "high" && "\u2713"}
                            </DropdownMenuItem>
                          </DropdownMenuSubContent>
                        </DropdownMenuSub>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>

                  {/* Sort dropdown */}
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button
                        type="button"
                        className={`flex h-8 shrink-0 items-center gap-1.5 rounded-full border px-2.5 text-xs ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1 transition-colors ${
                          activeSort
                            ? "border-primary/30 bg-primary/5 text-foreground"
                            : "border-input bg-white text-muted-foreground hover:bg-gray-50"
                        }`}
                      >
                        <span className="flex min-w-0 items-center gap-1.5">
                          {activeSort ? (
                            <>
                              {activeSort.icon}
                              <span className="truncate max-w-[140px]">{activeSort.label}</span>
                            </>
                          ) : (
                            <span>Sort by</span>
                          )}
                        </span>
                        <ChevronDown className="h-3 w-3 shrink-0 opacity-50" />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="min-w-[10rem]">
                      {activeSort && (
                        <DropdownMenuItem
                          onClick={() => {
                            setOrderBy("");
                            setSortDirection("desc");
                            setCurrentPage(1);
                            updateUrlParams({ page: 1 });
                          }}
                          className="text-muted-foreground"
                        >
                          Clear sort
                        </DropdownMenuItem>
                      )}
                      <DropdownMenuSub>
                        <DropdownMenuSubTrigger className="flex items-center gap-2">
                          <ThumbsDown className="h-4 w-4 text-red-600" />
                          Thumbs Down
                        </DropdownMenuSubTrigger>
                        <DropdownMenuSubContent>
                          <DropdownMenuItem onClick={() => applySort("thumbs_down_count", "desc")}>
                            High to low
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => applySort("thumbs_down_count", "asc")}>
                            Low to high
                          </DropdownMenuItem>
                        </DropdownMenuSubContent>
                      </DropdownMenuSub>
                      <DropdownMenuSub>
                        <DropdownMenuSubTrigger className="flex items-center gap-2">
                          <ThumbsUp className="h-4 w-4 text-green-600" />
                          Thumbs Up
                        </DropdownMenuSubTrigger>
                        <DropdownMenuSubContent>
                          <DropdownMenuItem onClick={() => applySort("thumbs_up_count", "desc")}>
                            High to low
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => applySort("thumbs_up_count", "asc")}>
                            Low to high
                          </DropdownMenuItem>
                        </DropdownMenuSubContent>
                      </DropdownMenuSub>
                      <DropdownMenuSub>
                        <DropdownMenuSubTrigger className="flex items-center gap-2">
                          <SmileIcon className="h-4 w-4" style={{ color: "#10b981" }} />
                          Customer Satisfaction
                        </DropdownMenuSubTrigger>
                        <DropdownMenuSubContent>
                          <DropdownMenuItem onClick={() => applySort("customer_satisfaction", "desc")}>
                            High to low
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => applySort("customer_satisfaction", "asc")}>
                            Low to high
                          </DropdownMenuItem>
                        </DropdownMenuSubContent>
                      </DropdownMenuSub>
                      <DropdownMenuSub>
                        <DropdownMenuSubTrigger className="flex items-center gap-2">
                          <Award className="h-4 w-4" style={{ color: "#8b5cf6" }} />
                          Quality of Service
                        </DropdownMenuSubTrigger>
                        <DropdownMenuSubContent>
                          <DropdownMenuItem onClick={() => applySort("quality_of_service", "desc")}>
                            High to low
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => applySort("quality_of_service", "asc")}>
                            Low to high
                          </DropdownMenuItem>
                        </DropdownMenuSubContent>
                      </DropdownMenuSub>
                      <DropdownMenuSub>
                        <DropdownMenuSubTrigger className="flex items-center gap-2">
                          <CheckCircle className="h-4 w-4" style={{ color: "#f59e0b" }} />
                          Resolution Rate
                        </DropdownMenuSubTrigger>
                        <DropdownMenuSubContent>
                          <DropdownMenuItem onClick={() => applySort("resolution_rate", "desc")}>
                            High to low
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => applySort("resolution_rate", "asc")}>
                            Low to high
                          </DropdownMenuItem>
                        </DropdownMenuSubContent>
                      </DropdownMenuSub>
                      <DropdownMenuSub>
                        <DropdownMenuSubTrigger className="flex items-center gap-2">
                          <Zap className="h-4 w-4" style={{ color: "#06b6d4" }} />
                          Efficiency
                        </DropdownMenuSubTrigger>
                        <DropdownMenuSubContent>
                          <DropdownMenuItem onClick={() => applySort("efficiency", "desc")}>
                            High to low
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => applySort("efficiency", "asc")}>
                            Low to high
                          </DropdownMenuItem>
                        </DropdownMenuSubContent>
                      </DropdownMenuSub>
                    </DropdownMenuContent>
                  </DropdownMenu>
                  <div className="flex items-center gap-1.5">
                    <Switch
                      id="hide-empty"
                      checked={hideEmpty}
                      onCheckedChange={(checked) => {
                        setHideEmpty(checked);
                        setCurrentPage(1);
                        updateUrlParams({ page: 1 });
                      }}
                      className="scale-75"
                    />
                    <Label htmlFor="hide-empty" className="text-xs text-muted-foreground cursor-pointer whitespace-nowrap">
                      Hide empty
                    </Label>
                  </div>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="outline"
                        size="icon"
                        className="h-8 w-8 shrink-0 rounded-full"
                        onClick={handleRefreshConversations}
                        disabled={loading}
                        aria-label="Refresh conversations"
                      >
                        <RefreshCw
                          className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`}
                          aria-hidden
                        />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>Refresh conversations</p>
                    </TooltipContent>
                  </Tooltip>
                </div>
              </div>

              <Card className="divide-y divide-gray-100 bg-white shadow-sm rounded-lg overflow-hidden">
                {loading ? (
                  <p className="text-center text-gray-500 p-6">
                    Loading transcripts...
                  </p>
                ) : error ? (
                  <p className="text-center text-red-500 p-6">
                    Error loading transcripts. Please try again.
                  </p>
                ) : paginatedTranscripts.length > 0 ? (
                  paginatedTranscripts.map((transcript) => {
                    const qualityScores = getQualityScores(transcript);
                    return (
                    <div
                      key={transcript.id}
                      onClick={() => {
                        setSelectedTranscript(transcript);
                        setIsLiveTranscriptSelected(isLiveTranscript(transcript));
                        setIsModalOpen(true);
                      }}
                      className="p-6 cursor-pointer transition-colors hover:bg-gray-50/80"
                    >
                      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                      <div className="flex items-start space-x-4 min-w-0">
                        <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/5">
                          {isCallTranscript(transcript) ? (
                            <PlayCircle className="w-5 h-5 text-primary" />
                          ) : (
                            <MessageSquare className="w-5 h-5 text-primary" />
                          )}
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <h3 className="font-semibold">
                              {isCallTranscript(transcript) ? "Call" : "Chat"} #
                              {(transcript?.metadata?.title ?? "----").slice(-4) || "Untitled"}{" - "}
                              {transcript?.metadata?.topic}
                            </h3>
                            {isLiveTranscript(transcript) && (
                              <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200 flex items-center gap-1 animate-pulse">
                                <Radio className="w-3 h-3" />
                                <span>Live</span>
                              </Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground">
                            <span>Duration: {formatDuration(transcript?.metadata?.duration ?? 0)}</span>
                            <span className="h-3 w-px bg-gray-200" aria-hidden />
                            <span>
                              {transcript?.timestamp
                                ? new Date(transcript.timestamp).toLocaleString()
                                : "N/A"}
                            </span>
                          </div>
                          {/* Quality score badges */}
                          {qualityScores && (
                            <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                              {qualityScores.map((s) => (
                                <Tooltip key={s.key}>
                                  <TooltipTrigger asChild>
                                    <span
                                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[11px] font-medium transition-opacity"
                                      style={getScoreBadgeStyle(s.color)}
                                    >
                                      {s.icon}
                                      {formatScorePercentage(s.value)}
                                    </span>
                                  </TooltipTrigger>
                                  <TooltipContent side="bottom" className="text-xs">
                                    {s.label}: {formatScorePercentage(s.value)}
                                  </TooltipContent>
                                </Tooltip>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                        <div className="flex flex-col items-end gap-2 shrink-0 mt-2 sm:mt-0">
                          {/* Sentiment badge */}
                          {(() => {
                            const sentiment = transcript ? getEffectiveSentiment(transcript) : "Unknown";
                            const cfg = SENTIMENT_CONFIG[sentiment.toLowerCase()] || DEFAULT_SENTIMENT;
                            return (
                              <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${cfg.bg} ${cfg.text} ${cfg.border}`}>
                                {cfg.icon}
                                {sentiment}
                              </span>
                            );
                          })()}
                          {/* Thumbs + supervisor feedback */}
                          <div className="flex items-center gap-2">
                            {transcript?.feedback && transcript.feedback.length > 0 && (() => {
                              const latestFeedback = transcript.feedback[transcript.feedback.length - 1];
                              const isGoodFeedback = latestFeedback.feedback === "good";
                              const message = latestFeedback.feedback_message?.trim() || "";
                              const tooltipText = message
                                ? `Supervisor feedback: ${message}`
                                : "Supervisor feedback.";
                              return (
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[11px] font-medium cursor-default ${isGoodFeedback ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-rose-50 text-rose-600 border-rose-200"}`}>
                                      {isGoodFeedback ? (
                                        <ThumbsUp className="w-3 h-3 shrink-0" />
                                      ) : (
                                        <ThumbsDown className="w-3 h-3 shrink-0" />
                                      )}
                                      Reviewed
                                    </span>
                                  </TooltipTrigger>
                                  <TooltipContent>{tooltipText}</TooltipContent>
                                </Tooltip>
                              );
                            })()}
                            <div className="flex items-center gap-0.5 text-xs text-muted-foreground">
                              <ThumbsUp className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                              <span className="tabular-nums min-w-[12px] text-center">{transcript?.thumbs_up_count ?? 0}</span>
                            </div>
                            <div className="flex items-center gap-0.5 text-xs text-muted-foreground">
                              <ThumbsDown className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                              <span className="tabular-nums min-w-[12px] text-center">{transcript?.thumbs_down_count ?? 0}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                    );
                  })
                ) : (
                    <p className="text-center text-gray-500 p-6">
                      No transcripts found. Try adjusting your filters.
                    </p>
                )}
              </Card>

              <PaginationBar
                total={totalCount}
                pageSize={ITEMS_PER_PAGE}
                currentPage={pagination.safePage}
                pageItemCount={pageItemCount}
                onPageChange={handlePageChange}
              />
            </div>
          </div>
        </main>
      </div>
      <UploadMediaDialog
        isOpen={isUploadDialogOpen}
        onOpenChange={setIsUploadDialogOpen}
      />
      {isLiveTranscriptSelected ? (
        <ActiveConversationDialog
          transcript={selectedTranscript}
          isOpen={isModalOpen}
          onOpenChange={setIsModalOpen}
          refetchConversations={refetch}
          onTakeOver={handleTakeOver}
        />
      ) : (
        <TranscriptDialog
          transcript={selectedTranscript}
          isOpen={isModalOpen}
          onOpenChange={setIsModalOpen}
        />
      )}
    </SidebarProvider>
  );
};

export default Transcripts;
