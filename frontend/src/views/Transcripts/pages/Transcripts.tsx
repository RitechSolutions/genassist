import { SidebarProvider } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import {
  MessageSquare,
  Search,
  PlayCircle,
  CheckCircle,
  MinusCircle,
  AlertCircle,
  XCircle,
  ChevronLeft,
  ChevronRight,
  Radio
} from "lucide-react";
import { Card } from "@/components/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/tabs";
import { useIsMobile } from "@/hooks/useMobile";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { useState, useEffect } from "react";
import { Transcript } from "@/interfaces/transcript.interface";
import { TranscriptDialog } from "../components/TranscriptDialog";
import { ActiveConversationDialog } from "@/views/ActiveConversations/components/ActiveConversationDialog";
import { useTranscriptData } from "../hooks/useTranscriptData";
import { getSentimentStyles } from "../helpers/formatting";
import { Badge } from "@/components/badge";
import { Switch } from "@/components/switch";
import { useLocation, useNavigate } from "react-router-dom";

const ITEMS_PER_PAGE = 10;

const Transcripts = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const searchParams = new URLSearchParams(location.search);
  
  const { data, loading, error, refetch } = useTranscriptData();
  const [selectedTranscript, setSelectedTranscript] = useState<Transcript | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isLiveTranscriptSelected, setIsLiveTranscriptSelected] = useState(false);
  const [activeTab, setActiveTab] = useState(searchParams.get("sentiment") || "all");
  const [supportType, setSupportType] = useState(searchParams.get("type") || "all");
  const [searchQuery, setSearchQuery] = useState(searchParams.get("query") || "");
  const [currentPage, setCurrentPage] = useState(parseInt(searchParams.get("page") || "1", 10));
  
  // Initialize showLiveOnly based on URL parameters
  const statusParams = searchParams.getAll("status");
  const [showLiveOnly, setShowLiveOnly] = useState(
    statusParams.includes("in_progress") && statusParams.includes("takeover")
  );
  
  const isMobile = useIsMobile();
  const transcripts = Array.isArray(data) ? data : [];

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

  const handleLiveOnlyToggle = (checked: boolean) => {
    setShowLiveOnly(checked);
    
    if (checked) {
      updateUrlParams({ status: ["in_progress", "takeover"] });
    } else {
      updateUrlParams({ status: null });
    }
    
    setCurrentPage(1);
  };

  const isLiveTranscript = (transcript: Transcript) => {
    return transcript?.status === "in_progress" || transcript?.status === "takeover";
  };

  const isCallTranscript = (transcript: Transcript) => {
    return Boolean(transcript?.recording_id) || Boolean(transcript?.metadata?.isCall);
  };

  useEffect(() => {
    refetch?.();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    
    // Update filter states based on URL
    setActiveTab(params.get("sentiment") || "all");
    setSupportType(params.get("type") || "all");
    setSearchQuery(params.get("query") || "");
    setCurrentPage(parseInt(params.get("page") || "1", 10));
    
    const statusValues = params.getAll("status");
    setShowLiveOnly(
      statusValues.includes("in_progress") && statusValues.includes("takeover")
    );
  }, [location.search]);

  // Handle filter changes
  const handleSentimentChange = (value: string) => {
    setActiveTab(value);
    updateUrlParams({ sentiment: value === "all" ? null : value, page: 1 });
  };

  const handleSupportTypeChange = (value: string) => {
    setSupportType(value);
    updateUrlParams({ type: value === "all" ? null : value, page: 1 });
  };

  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    updateUrlParams({ query: value || null, page: 1 });
  };

  const handlePageChange = (newPage: number) => {
    setCurrentPage(newPage);
    updateUrlParams({ page: newPage === 1 ? null : newPage });
  };

  const filteredTranscripts = transcripts.filter((transcript) => {
    if (showLiveOnly && !isLiveTranscript(transcript)) {
      return false;
    }
    
    const title = transcript?.metadata?.title?.toLowerCase() || "";
    const topic = transcript?.metadata?.topic?.toLowerCase() || "";
    const sentiment = transcript?.metrics?.sentiment?.toLowerCase() || "";
    const searchLower = searchQuery.toLowerCase().trim();
    
    const matchesSearch =
      searchQuery.trim() === "" ||
      title.includes(searchLower) ||
      topic.includes(searchLower);
  
    const matchesSentiment = activeTab === "all" || sentiment === activeTab;
  
    const matchesSupportType =
      supportType === "all" || topic.includes(supportType.toLowerCase());
  
    return matchesSearch && matchesSentiment && matchesSupportType;
  });

  const totalPages = Math.ceil(filteredTranscripts.length / ITEMS_PER_PAGE);
  const paginatedTranscripts = filteredTranscripts.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE
  );

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full">
        {!isMobile && <AppSidebar />}
        <main className="flex-1 flex flex-col bg-zinc-100">
          <div className="flex-1 p-8">
            <div className="max-w-7xl mx-auto space-y-6">
              <div className="flex justify-between items-start">
                <div>
                  <h1 className="text-3xl font-bold mb-2 animate-fade-down">
                    Transcripts
                  </h1>
                  <p className="text-muted-foreground animate-fade-up">
                    Review and analyze your conversation transcripts
                  </p>
                </div>
                <div className="flex gap-4">
                  <div className="flex items-center gap-2 bg-white border rounded-lg px-3 py-2 shadow-sm">
                    <Radio className="w-4 h-4 text-green-500" />
                    <span className="text-sm font-medium">Live Only</span>
                    <Switch 
                      checked={showLiveOnly} 
                      onCheckedChange={handleLiveOnlyToggle}
                    />
                  </div>
                  <Select value={supportType} onValueChange={handleSupportTypeChange}>
                    <SelectTrigger className="w-[180px]">
                      <SelectValue placeholder="Support Type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Types</SelectItem>
                      <SelectItem value="Product Inquiry">
                        Product Inquiry
                      </SelectItem>
                      <SelectItem value="Technical Support">
                        Technical Support
                      </SelectItem>
                      <SelectItem value="Billing Question">
                        Billing Questions
                      </SelectItem>
                      <SelectItem value="Other">Other</SelectItem>
                    </SelectContent>
                  </Select>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                    <input
                      type="text"
                      placeholder="Search transcripts..."
                      value={searchQuery}
                      onChange={(e) => handleSearchChange(e.target.value)}
                      className="w-full pl-10 pr-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                </div>
              </div>

              <Tabs
                value={activeTab}
                className="w-full"
                onValueChange={handleSentimentChange}
              >
                <TabsList className="grid w-full grid-cols-5 lg:w-[500px]">
                  <TabsTrigger value="all" className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4" />
                    All
                  </TabsTrigger>
                  <TabsTrigger
                    value="positive"
                    className="flex items-center gap-2"
                  >
                    <CheckCircle className="w-4 h-4 text-green-500" />
                    Positive
                  </TabsTrigger>
                  <TabsTrigger
                    value="neutral"
                    className="flex items-center gap-2"
                  >
                    <MinusCircle className="w-4 h-4 text-yellow-500" />
                    Neutral
                  </TabsTrigger>
                  <TabsTrigger
                  value="negative"
                  className="flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 text-orange-400" />
                    Bad
                  </TabsTrigger>
                  <TabsTrigger
                  value="very-bad"
                  className="flex items-center gap-2">
                    <XCircle className="w-4 h-4 text-red-500" />
                    Very Bad
                  </TabsTrigger>
                </TabsList>
              </Tabs>

              <Card className="divide-y bg-white">
                {loading ? (
                  <p className="text-center text-gray-500 p-6">
                    Loading transcripts...
                  </p>
                ) : error ? (
                  <p className="text-center text-red-500 p-6">
                    Error loading transcripts. Please try again.
                  </p>
                ) : paginatedTranscripts.length > 0 ? (
                  paginatedTranscripts.map((transcript) => (
                    <div
                      key={transcript.id}
                      onClick={() => {
                        setSelectedTranscript(transcript);
                        setIsLiveTranscriptSelected(isLiveTranscript(transcript));
                        setIsModalOpen(true);
                      }}
                      className="p-6 cursor-pointer transition-colors hover:bg-gray-50"
                    >
                      <div className="flex items-start justify-between">
                      <div className="flex items-start space-x-4">
                        {isCallTranscript(transcript) ? (
                          <PlayCircle className="w-6 h-6 text-primary mt-1" />
                        ) : (
                          <MessageSquare className="w-6 h-6 text-primary mt-1" />
                        )}
                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="font-semibold">
                              {isCallTranscript(transcript) ? "Call" : "Chat"} #
                              {(transcript?.metadata?.title ?? "----").slice(0, 4)|| "Untitled"}{" - "} 
                              {transcript?.metadata?.topic}
                            </h3>
                            {isLiveTranscript(transcript) && (
                              <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200 flex items-center gap-1 animate-pulse">
                                <Radio className="w-3 h-3" />
                                <span>Live</span>
                              </Badge>
                            )}
                          </div>
                          <p className="text-sm text-muted-foreground mt-1">
                            Duration: {transcript?.metadata?.duration ?? "N/A"}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            Date:{" "}
                            {transcript?.timestamp
                              ? new Date(transcript.timestamp).toLocaleString()
                              : "N/A"}
                          </p>
                        </div>
                      </div>
                        <div className="text-right">
                          <span
                            className={`inline-block px-3 py-1 rounded-full text-xs font-medium ${getSentimentStyles(
                              transcript && transcript.metrics ? transcript.metrics.sentiment : ""
                            )}`}
                          >
                            {transcript && transcript.metrics ? transcript.metrics.sentiment : "Unknown"}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))
                ) : (
                    <p className="text-center text-gray-500 p-6">
                      No transcripts found. Try adjusting your filters.
                    </p>
                )}
              </Card>

              {totalPages > 1 && (
                <div className="flex items-center justify-between pt-4">
                  <div className="text-sm text-muted-foreground">
                    Showing {filteredTranscripts.length > 0 ? (currentPage - 1) * ITEMS_PER_PAGE + 1 : 0} to{" "}
                    {Math.min(
                      currentPage * ITEMS_PER_PAGE,
                      filteredTranscripts.length
                    )}{" "}
                    of {filteredTranscripts.length} results
                  </div>
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => handlePageChange(Math.max(1, currentPage - 1))}
                      disabled={currentPage === 1}
                      className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <ChevronLeft className="w-5 h-5" />
                    </button>
                    {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                      let pageNumber;
                      
                      if (totalPages <= 5) {
                        pageNumber = i + 1;
                      } else if (currentPage <= 3) {
                        pageNumber = i + 1;
                      } else if (currentPage >= totalPages - 2) {
                        pageNumber = totalPages - 4 + i;
                      } else {
                        pageNumber = currentPage - 2 + i;
                      }
                      
                      return (
                        <button
                          key={i}
                          onClick={() => handlePageChange(pageNumber)}
                          className={`w-8 h-8 rounded-full ${
                            currentPage === pageNumber
                              ? "bg-primary text-white"
                              : "hover:bg-gray-100"
                          }`}
                        >
                          {pageNumber}
                        </button>
                      );
                    })}
                    <button
                      onClick={() => handlePageChange(Math.min(totalPages, currentPage + 1))}
                      disabled={currentPage === totalPages}
                      className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <ChevronRight className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </main>
      </div>
      {isLiveTranscriptSelected ? (
        <ActiveConversationDialog 
          transcript={selectedTranscript} 
          isOpen={isModalOpen} 
          onOpenChange={setIsModalOpen}
          refetchConversations={refetch}
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