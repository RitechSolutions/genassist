import { SidebarProvider, SidebarTrigger } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import {
  MessageSquare,
  Search,
  PlayCircle,
  CheckCircle,
  MinusCircle,
  AlertCircle,
  Radio,
  ThumbsUp,
  ThumbsDown,
  Upload,
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
import { useState, useEffect } from "react";
import { Transcript } from "@/interfaces/transcript.interface";
import { TranscriptDialog } from "../components/TranscriptDialog";
import { ActiveConversationDialog } from "@/views/ActiveConversations/components/ActiveConversationDialog";
import { useTranscriptData } from "../hooks/useTranscriptData";
import { formatDuration, getSentimentStyles, getEffectiveSentiment, HOSTILITY_POSITIVE_MAX, HOSTILITY_NEUTRAL_MAX } from "../helpers/formatting";
import { Badge } from "@/components/badge";
import { Switch } from "@/components/switch";
import { useLocation, useNavigate } from "react-router-dom";
import { useToast } from "@/hooks/useToast";
import { conversationService } from "@/services/liveConversations";
import { UploadMediaDialog } from "@/views/MediaUpload";
import { getPaginationMeta } from "@/helpers/pagination";
import { PaginationBar } from "@/components/PaginationBar";

const ITEMS_PER_PAGE = 10;

const Transcripts = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { toast } = useToast();
  const searchParams = new URLSearchParams(location.search);
  
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
  
  // Calculate hostility parameters based on sentiment
  const getHostilityParams = (sentiment: string) => {
    return { 
      hostility_positive_max: HOSTILITY_POSITIVE_MAX, 
      hostility_neutral_max: HOSTILITY_NEUTRAL_MAX 
    };
  };
  
  const hostilityParams = getHostilityParams(activeTab);
  
  const { data, total, loading, error, refetch } = useTranscriptData({ 
    limit: ITEMS_PER_PAGE,
    skip: (currentPage - 1) * ITEMS_PER_PAGE,
    sentiment: activeTab,
    hostility_positive_max: hostilityParams.hostility_positive_max,
    hostility_neutral_max: hostilityParams.hostility_neutral_max
  });
  
  // Initialize showLiveOnly based on URL parameters
  const statusParams = searchParams.getAll("status");
  const [showLiveOnly, setShowLiveOnly] = useState(
    statusParams.includes("in_progress") && statusParams.includes("takeover")
  );
  
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
    const params = new URLSearchParams(location.search);
    
    // Update filter states based on URL
    setActiveTab(params.get("sentiment") || "all");
    setSupportType(params.get("type") || "all");
    setSearchQuery(params.get("query") || "");
    setCurrentPage(
      Math.max(1, parseInt(params.get("page") || "1", 10) || 1)
    );
    
    const statusValues = params.getAll("status");
    setShowLiveOnly(
      statusValues.includes("in_progress") && statusValues.includes("takeover")
    );
  }, [location.search]);

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

  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    updateUrlParams({ query: value || null, page: 1 });
  };

  const handlePageChange = (newPage: number) => {
    const nextPage = Math.max(1, newPage);
    setCurrentPage(nextPage);
    updateUrlParams({ page: nextPage === 1 ? null : nextPage });
  };

  const filteredTranscripts = transcripts.filter((transcript) => {
    if (showLiveOnly && !isLiveTranscript(transcript)) {
      return false;
    }
    
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

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full overflow-x-hidden">
        {!isMobile && <AppSidebar />}
        <main className="flex-1 flex flex-col bg-zinc-100 min-w-0 relative">
          <SidebarTrigger className="fixed top-4 z-10 h-8 w-8 bg-white/50 backdrop-blur-sm hover:bg-white/70 rounded-full shadow-md transition-[left] duration-200" />
          <div className="flex-1 p-4 sm:p-6 lg:p-8">
            <div className="max-w-7xl mx-auto space-y-6 w-full">
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
                  <div className="flex items-center gap-2 bg-white border rounded-lg px-3 py-2 shadow-sm w-full sm:w-auto">
                    <Radio className="w-4 h-4 text-green-500" />
                    <span className="text-sm font-medium">Live Only</span>
                    <Switch 
                      checked={showLiveOnly} 
                      onCheckedChange={handleLiveOnlyToggle}
                    />
                  </div>
                  <Select value={supportType} onValueChange={handleSupportTypeChange}>
                    <SelectTrigger className="w-full sm:w-[180px]">
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
                  <div className="relative w-full sm:w-[260px]">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                    <input
                      type="text"
                      placeholder="Search conversations..."
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
                <TabsList className="w-full flex-wrap justify-start gap-2">
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
                  {/* <TabsTrigger
                  value="very-bad"
                  className="flex items-center gap-2">
                    <XCircle className="w-4 h-4 text-red-500" />
                    Very Bad
                  </TabsTrigger> */}
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
                      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                      <div className="flex items-start space-x-4 min-w-0">
                        {isCallTranscript(transcript) ? (
                          <PlayCircle className="w-6 h-6 text-primary mt-1" />
                        ) : (
                          <MessageSquare className="w-6 h-6 text-primary mt-1" />
                        )}
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
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
                            Duration: {formatDuration(transcript?.metadata?.duration ?? 0)}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            Date:{" "}
                            {transcript?.timestamp
                              ? new Date(transcript.timestamp).toLocaleString()
                              : "N/A"}
                          </p>
                        </div>
                      </div>
                        <div className="text-right flex items-center gap-2 sm:justify-end flex-wrap mt-2 sm:mt-0">
                          {/* Display conversation feedback */}
                          {transcript?.feedback && transcript.feedback.length > 0 && (() => {
                            const latestFeedback = transcript.feedback[transcript.feedback.length - 1];
                            const isGoodFeedback = latestFeedback.feedback === 'good';
                            return (
                              <div className="flex items-center gap-1 px-2 py-1 bg-gray-100 rounded-full">
                                {isGoodFeedback ? (
                                  <ThumbsUp className="w-3 h-3 text-green-600" />
                                ) : (
                                  <ThumbsDown className="w-3 h-3 text-red-600" />
                                )}
                                <span className="text-xs text-gray-700">
                                  {latestFeedback.feedback_message?.slice(0, 30) || 'Feedback provided'}
                                  {latestFeedback.feedback_message && latestFeedback.feedback_message.length > 30 ? '...' : ''}
                                </span>
                              </div>
                            );
                          })()}
                          <span
                            className={`inline-block px-3 py-1 rounded-full text-xs font-medium ${getSentimentStyles(
                              transcript ? getEffectiveSentiment(transcript) : ""
                            )}`}
                          >
                            {transcript ? getEffectiveSentiment(transcript) : "Unknown"}
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