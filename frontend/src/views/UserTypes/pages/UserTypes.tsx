import { SidebarProvider } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { UserTypesCard } from "@/views/UserTypes/components/UserTypesCard";
import { useIsMobile } from "@/hooks/useMobile";
import { Search, Plus } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/button";
import { UserTypeDialog } from "../components/UserTypeDialog";
import { UserType } from "@/interfaces/userType.interface";

export default function UserTypes() {
  const isMobile = useIsMobile();
  const [searchQuery, setSearchQuery] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create');
  const [userTypeToEdit, setUserTypeToEdit] = useState<UserType | null>(null);

  const handleUserTypeSaved = () => {
    setRefreshKey(prevKey => prevKey + 1);
  };

  const handleCreateUserType = () => {
    setDialogMode('create');
    setUserTypeToEdit(null);
    setIsDialogOpen(true);
  };
  
  const handleEditUserType = (userType: UserType) => {
    setDialogMode('edit');
    setUserTypeToEdit(userType);
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
                  <h1 className="text-3xl font-bold mb-2 animate-fade-down">User Types</h1>
                  <p className="text-muted-foreground animate-fade-up">View and manage system user types</p>
                </div>
                <div className="flex items-center gap-4">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                    <input
                      type="text"
                      placeholder="Search user types..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full pl-10 pr-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                  <Button 
                    className="flex items-center gap-2"
                    onClick={handleCreateUserType}
                  >
                    <Plus className="w-4 h-4" />
                    Add New User Type
                  </Button>
                </div>
              </div>
              <UserTypesCard 
                searchQuery={searchQuery} 
                refreshKey={refreshKey}
                onEditUserType={handleEditUserType}
              />
            </div>
          </div>
        </main>
      </div>
      <UserTypeDialog 
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onUserTypeSaved={handleUserTypeSaved}
        userTypeToEdit={userTypeToEdit}
        mode={dialogMode}
      />
    </SidebarProvider>
  );
} 