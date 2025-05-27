import { SidebarProvider } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { UsersCard } from "@/views/Users/components/UsersCard";
import { useIsMobile } from "@/hooks/useMobile";
import { Search, Plus } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/button";
import { UserDialog } from "../components/UserDialog";
import { User } from "@/interfaces/user.interface";

export default function Users() {
  const isMobile = useIsMobile();
  const [searchQuery, setSearchQuery] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create');
  const [userToEdit, setUserToEdit] = useState<User | null>(null);

  const handleUserSaved = () => {
    setRefreshKey(prevKey => prevKey + 1);
  };

  const handleCreateUser = () => {
    setDialogMode('create');
    setUserToEdit(null);
    setIsDialogOpen(true);
  };
  
  const handleEditUser = (user: User) => {
    setDialogMode('edit');
    setUserToEdit(user);
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
                  <h1 className="text-3xl font-bold mb-2 animate-fade-down">Users</h1>
                  <p className="text-muted-foreground animate-fade-up">View and manage system users</p>
                </div>
                <div className="flex items-center gap-4">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                    <input
                      type="text"
                      placeholder="Search users..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full pl-10 pr-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                  <Button 
                    className="flex items-center gap-2"
                    onClick={handleCreateUser}
                  >
                    <Plus className="w-4 h-4" />
                    Add New User
                  </Button>
                </div>
              </div>
              <UsersCard 
                searchQuery={searchQuery} 
                refreshKey={refreshKey} 
                onEditUser={handleEditUser}
              />
            </div>
          </div>
        </main>
      </div>
      <UserDialog 
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onUserCreated={handleUserSaved}
        userToEdit={userToEdit}
        mode={dialogMode}
      />
    </SidebarProvider>
  );
} 