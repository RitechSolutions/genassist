import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/button";
import { ArrowLeft } from "lucide-react";
import { SidebarProvider, SidebarTrigger } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { useIsMobile } from "@/hooks/useMobile";
import SecurityPanel from "@/views/AIAgents/components/Customer/SecurityPanel";

export default function SecurityPage() {
  const { agentId } = useParams<{ agentId: string }>();
  const navigate = useNavigate();

  return (
    <main className="flex-1 flex flex-col bg-zinc-100 min-w-0 relative">
      <SidebarTrigger className="fixed top-4 z-10 h-8 w-8 bg-white/50 backdrop-blur-sm hover:bg-white/70 rounded-full shadow-md transition-[left] duration-200" />
      <div className="flex-1 p-4 sm:p-6 lg:p-8">
        <div className="w-full space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => navigate("/ai-agents")}
                className="rounded-full"
                aria-label="Back to AI Agents"
              >
                <ArrowLeft className="h-4 w-4" />
              </Button>
              <div>
                <h2 className="text-3xl font-bold">Security Settings</h2>
                <p className="text-zinc-400 font-normal mt-1">
                  Configure security settings for your agent
                </p>
              </div>
            </div>
          </div>

          <SecurityPanel agentId={agentId} />
        </div>
      </div>
    </main>
  );
}
