import { SidebarProvider, SidebarTrigger } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { OperatorsCard } from "@/views/Operators/components/OperatorCard";
import { useIsMobile } from "@/hooks/useMobile";
import { Plus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/button";
import { Operator } from "@/interfaces/operator.interface";
import { CreateOperator } from "../components/CreateOperator";
import { OperatorCredentialsDialog } from "../components/OperatorCredentialsDialog";
import { SearchInput } from "@/components/SearchInput";

type NewOperatorResponse = Operator & {
  user: {
    username: string;
    email: string;
    password: string;
  };
};

export default function Operators() {
  const isMobile = useIsMobile();
  const [searchQuery, setSearchQuery] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  const [refreshKey, setRefreshKey] = useState(0);
  const [newOperatorCredentials, setNewOperatorCredentials] = useState<{
    username: string;
    email: string;
    password: string;
  } | null>(null);
  const [isCredentialsDialogOpen, setIsCredentialsDialogOpen] = useState(false);

  const handleCreateOperator = () => {
    setIsDialogOpen(true);
  };

  const handleOperatorSaved = (newOperator: NewOperatorResponse) => {
    setRefreshKey((prev) => prev + 1);
    setIsDialogOpen(false);
    if (newOperator && newOperator.user && newOperator.user.password) {
      setNewOperatorCredentials({
        username: newOperator.user.username,
        email: newOperator.user.email,
        password: newOperator.user.password,
      });
      setIsCredentialsDialogOpen(true);
    }
  };


  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full overflow-x-hidden">
        {!isMobile && <AppSidebar />}
        <main className="flex-1 flex flex-col bg-zinc-100 min-w-0 relative peer-data-[state=expanded]:md:ml-[calc(var(--sidebar-width)-2px)] peer-data-[state=collapsed]:md:ml-0 transition-[margin] duration-200">
          <SidebarTrigger className="fixed top-4 z-10 h-8 w-8 bg-white/50 backdrop-blur-sm hover:bg-white/70 rounded-full shadow-md transition-[left] duration-200" />
          <div className="flex-1 p-4 sm:p-6 lg:p-8">
            <div className="max-w-7xl mx-auto space-y-6 w-full">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between sm:flex-wrap">
                <div className="min-w-0">
                  <h1 className="text-2xl md:text-3xl font-bold mb-1 animate-fade-down">Operators</h1>
                  <p className="text-sm md:text-base text-muted-foreground animate-fade-up">View and manage your team of customer service operators</p>
                </div>
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 sm:gap-4 w-full sm:w-auto">
                  <SearchInput
                    placeholder="Search operators..."
                    value={searchQuery}
                    onChange={setSearchQuery}
                  />
                  <Button
                    className="flex items-center gap-2 w-full sm:w-auto justify-center rounded-full"
                    onClick={handleCreateOperator}
                  >
                    <Plus className="w-4 h-4" />
                    Create New Operator
                  </Button>
                </div>
              </div>
              <OperatorsCard
                searchQuery={searchQuery}
                refreshKey={refreshKey} />

            </div>
          </div>
        </main>
      </div>

      <CreateOperator
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onOperatorCreated={handleOperatorSaved}
      />

      <OperatorCredentialsDialog
        isOpen={isCredentialsDialogOpen}
        onOpenChange={setIsCredentialsDialogOpen}
        credentials={newOperatorCredentials}
      />

    </SidebarProvider>
  );
}
