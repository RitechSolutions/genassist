import { useParams, useNavigate } from "react-router-dom";
import { SidebarTrigger } from "@/components/sidebar";
import SchedulingView from "@/views/AIAgents/Scheduling/SchedulingView";

export default function SchedulingPage() {
  const { agentId } = useParams<{ agentId: string }>();
  const navigate = useNavigate();

  return (
    <main className="flex-1 flex flex-col bg-zinc-100 min-w-0 relative">
      <SidebarTrigger className="fixed top-6 z-10 h-8 w-8 bg-white/50 backdrop-blur-sm hover:bg-white/70 rounded-full shadow-md transition-[left] duration-200" />
      <div className="flex-1 p-4 sm:p-6 lg:p-8">
        <div className="max-w-7xl mx-auto">
          <SchedulingView
            agentId={agentId}
            onBack={() => navigate("/ai-agents")}
          />
        </div>
      </div>
    </main>
  );
}
