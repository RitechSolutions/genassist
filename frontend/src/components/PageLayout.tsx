import { ReactNode } from "react";
import { SidebarProvider } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { useIsMobile } from "@/hooks/useMobile";

interface PageLayoutProps {
  children: ReactNode;
}

export function PageLayout({ children }: PageLayoutProps) {
  const isMobile = useIsMobile();

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full">
        {!isMobile && <AppSidebar />}
        <main className="flex-1 flex flex-col bg-zinc-100">
          <div className="flex-1 p-8">
            <div className="max-w-2xl xl:max-w-7xl mx-auto space-y-6">
              {children}
            </div>
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
} 