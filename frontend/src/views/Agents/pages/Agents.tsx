import { SidebarProvider } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { AgentsCard } from "@/views/Agents/components/AgentsCard";
import { useIsMobile } from "@/hooks/useMobile";
import { Search } from "lucide-react";
import { useState } from "react";

export default function Agents() {
  const isMobile = useIsMobile();
  const [searchQuery, setSearchQuery] = useState("");

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full">
        {!isMobile && <AppSidebar />}
        <main className="flex-1 flex flex-col bg-zinc-100">
          <div className="flex-1 p-8">
            <div className="max-w-7xl mx-auto space-y-6">
              <div className="flex justify-between items-start">
                <div>
                  <h1 className="text-3xl font-bold mb-2 animate-fade-down">Operators</h1>
                  <p className="text-muted-foreground animate-fade-up">View and manage your team of customer service operators</p>
                </div>
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                  <input
                    type="text"
                    placeholder="Search operators..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-10 pr-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
              </div>
              <AgentsCard searchQuery={searchQuery}/>
            </div>
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
}
