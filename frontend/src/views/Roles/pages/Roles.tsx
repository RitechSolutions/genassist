import { SidebarProvider } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { RolesCard } from "@/views/Roles/components/RolesCard";
import { RoleDialog } from "@/views/Roles/components/RoleDialog";
import { useIsMobile } from "@/hooks/useMobile";
import { Search, Plus } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/button";
import { Role } from "@/interfaces/role.interface";

export default function Roles() {
  const isMobile = useIsMobile();
  const [searchQuery, setSearchQuery] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create');
  const [roleToEdit, setRoleToEdit] = useState<Role | null>(null);

  const handleRoleSaved = () => {
    setRefreshKey(prevKey => prevKey + 1);
  };

  const handleCreateRole = () => {
    setDialogMode('create');
    setRoleToEdit(null);
    setIsDialogOpen(true);
  };
  
  const handleEditRole = (role: Role) => {
    setDialogMode('edit');
    setRoleToEdit(role);
    setIsDialogOpen(true);
  };

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full">
        {!isMobile && <AppSidebar />}
        <main className="flex-1 flex flex-col bg-zinc-100">
          <div className="flex-1 p-8">
            <div className="max-w-7xl mx-auto space-y-6">
              <div className="flex justify-between items-start">
                <div>
                  <h1 className="text-3xl font-bold mb-2 animate-fade-down">Roles</h1>
                  <p className="text-muted-foreground animate-fade-up">View and manage system roles</p>
                </div>
                <div className="flex items-center gap-4">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                    <input
                      type="text"
                      placeholder="Search roles..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full pl-10 pr-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                  <Button 
                    className="flex items-center gap-2"
                    onClick={handleCreateRole}
                  >
                    <Plus className="w-4 h-4" />
                    Add New Role
                  </Button>
                </div>
              </div>
              <RolesCard 
                searchQuery={searchQuery} 
                refreshKey={refreshKey}
                onEditRole={handleEditRole}
              />
            </div>
          </div>
        </main>
      </div>
      <RoleDialog 
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onRoleSaved={handleRoleSaved}
        roleToEdit={roleToEdit}
        mode={dialogMode}
      />
    </SidebarProvider>
  );
} 