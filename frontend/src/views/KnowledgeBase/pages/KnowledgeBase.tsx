import React from 'react';
import KnowledgeBaseManager from '../components/KnowledgeBaseManager';
import { SidebarProvider } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { useIsMobile } from "@/hooks/useMobile";

const KnowledgeBase: React.FC = () => {
  const isMobile = useIsMobile();
  
  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full">
        {!isMobile && <AppSidebar />}
        <main className="flex-1 flex flex-col bg-zinc-100">
          <div className="flex-1 p-8">
            <div className="max-w-7xl mx-auto">
              <KnowledgeBaseManager />
            </div>
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
};

export default KnowledgeBase; 