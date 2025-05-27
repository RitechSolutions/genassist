import { useEffect, useState } from "react";
import { getAllDataSources, deleteDataSource } from "@/services/dataSources";
import { SidebarProvider } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { DataSourceCard } from "@/views/DataSources/components/DataSourceCard";
import { useIsMobile } from "@/hooks/useMobile";
import { Search, Plus } from "lucide-react";
import { Button } from "@/components/button";
import { DataSourceDialog } from "../components/DataSourceDialog";
import { DataSource } from "@/interfaces/dataSource.interface";
import toast from "react-hot-toast";

export default function DataSources() {
  const isMobile = useIsMobile();
  const [searchQuery, setSearchQuery] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">("create");
  const [dataSourceToEdit, setDataSourceToEdit] = useState<DataSource | null>(
    null
  );

  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  
  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        const data = await getAllDataSources();
        setDataSources(data);
      } catch (error) {
        console.error("Failed to fetch data sources:", error);
      } finally {
        setIsLoading(false);
      }
    };
  
    fetchData();
  }, [refreshKey]);

  const handleDataSourceSaved = () => {
    setRefreshKey((prevKey) => prevKey + 1);
  };

  const handleCreateDataSource = () => {
    setDialogMode("create");
    setDataSourceToEdit(null);
    setIsDialogOpen(true);
  };

  const handleEditDataSource = (dataSource: DataSource) => {
    setDialogMode("edit");
    setDataSourceToEdit(dataSource);
    setIsDialogOpen(true);
  };

  const handleDeleteDataSource = async (id: string) => {
    try {
      await deleteDataSource(id);
      toast.success("Data source deleted");
      setRefreshKey((prev) => prev + 1);
    } catch (error) {
      toast.error("Failed to delete data source");
    }
  };
  
  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full">
        {!isMobile && <AppSidebar />}
        <main className="flex-1 flex flex-col bg-zinc-100">
          <div className="flex-1 p-8">
            <div className="max-w-2xl xl:max-w-7xl mx-auto space-y-6">
              <div className="flex justify-between items-start">
                <div>
                  <h1 className="text-3xl font-bold mb-2 animate-fade-down">
                    Data Sources
                  </h1>
                  <p className="text-muted-foreground animate-fade-up">
                    View and manage system data sources
                  </p>
                </div>
                <div className="flex items-center gap-4">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                    <input
                      type="text"
                      placeholder="Search data sources..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full pl-10 pr-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                  <Button
                    className="flex items-center gap-2"
                    onClick={handleCreateDataSource}
                  >
                    <Plus className="w-4 h-4" />
                    Add New Data Source
                  </Button>
                </div>
              </div>
              <DataSourceCard
                searchQuery={searchQuery}
                refreshKey={refreshKey}
                dataSources={dataSources}
                onEditDataSource={handleEditDataSource}
                onDeleteDataSource={handleDeleteDataSource} 
              />
            </div>
          </div>
        </main>
      </div>
      <DataSourceDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onDataSourceSaved={handleDataSourceSaved}
        dataSourceToEdit={dataSourceToEdit}
        mode={dialogMode}
      />
    </SidebarProvider>
  );
}