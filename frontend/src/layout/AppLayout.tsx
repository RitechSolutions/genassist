import { Outlet } from "react-router-dom";
import { SidebarProvider, SidebarTrigger } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";

export default function AppLayout() {
  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full overflow-x-hidden">
        <AppSidebar />
        <main className="flex-1 flex flex-col bg-zinc-100 dark:bg-zinc-950 min-w-0 relative peer-data-[state=expanded]:md:ml-[calc(var(--sidebar-width)-2px)] peer-data-[state=collapsed]:md:ml-0 transition-[margin] duration-200">
          <SidebarTrigger className="fixed top-6 z-10 h-8 w-8 bg-white/50 dark:bg-zinc-800/60 text-zinc-700 dark:text-zinc-200 backdrop-blur-sm hover:bg-white/70 dark:hover:bg-zinc-700/70 rounded-full shadow-md transition-[left] duration-200" />
          <Outlet />
        </main>
      </div>
    </SidebarProvider>
  );
}
