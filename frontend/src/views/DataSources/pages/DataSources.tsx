import { useEffect, useState } from "react";
import { getAllDataSources, deleteDataSource } from "@/services/dataSources";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { DataSourceCard } from "@/views/DataSources/components/DataSourceCard";
import { DataSourceDialog } from "../components/DataSourceDialog";
import { DataSource } from "@/interfaces/dataSource.interface";
import toast from "react-hot-toast";

export default function DataSources() {
  const [searchQuery, setSearchQuery] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">("create");
  const [dataSourceToEdit, setDataSourceToEdit] = useState<DataSource | null>(
    null
  );

  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const data = await getAllDataSources();
        setDataSources(data);
      } catch (error) {
        setError("We couldn't load your data sources. Please try again.");
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [refreshKey]);

  const handleRetry = () => setRefreshKey((prevKey) => prevKey + 1);

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
      //toast.success("Data source deleted successfully.");
      setRefreshKey((prev) => prev + 1);
    } catch (error) {
      toast.error("Failed to delete data source.");
    }
  };

  return (
    <PageLayout>
      <PageHeader
        title="Data Sources"
        subtitle="View and manage system data sources"
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search data sources..."
        actionButtonText="Add New Data Source"
        onActionClick={handleCreateDataSource}
      />

      <DataSourceCard
        searchQuery={searchQuery}
        refreshKey={refreshKey}
        dataSources={dataSources}
        loading={isLoading}
        error={error}
        onRetry={handleRetry}
        onCreateDataSource={handleCreateDataSource}
        onEditDataSource={handleEditDataSource}
        onDeleteDataSource={handleDeleteDataSource}
      />

      <DataSourceDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onDataSourceSaved={handleDataSourceSaved}
        dataSourceToEdit={dataSourceToEdit}
        mode={dialogMode}
      />
    </PageLayout>
  );
}
