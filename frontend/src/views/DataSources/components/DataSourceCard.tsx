import { useState } from "react";
import { DataTable, Column } from "@/components/ui/data-table";
import { LIST_PAGE_SIZE } from "@/constants/pagination";
import { ActionButtons } from "@/components/ActionButtons";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Badge } from "@/components/badge";
import { DataSource } from "@/interfaces/dataSource.interface";
import { toast } from "react-hot-toast";
import { CheckCircle, AlertCircle, HelpCircle } from "lucide-react";

interface DataSourceCardProps {
  dataSources: DataSource[];
  searchQuery: string;
  refreshKey: number;
  loading?: boolean;
  onEditDataSource?: (dataSource: DataSource) => void;
  onDeleteDataSource?: (id: string) => Promise<void>;
}

export function DataSourceCard({
  searchQuery,
  dataSources,
  loading = false,
  onEditDataSource,
  onDeleteDataSource,
}: DataSourceCardProps) {
  const [error, setError] = useState<string | null>(null);
  const [dataSourceToDelete, setDataSourceToDelete] =
    useState<DataSource | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const filteredDataSources = dataSources.filter((dataSource) => {
    const name = dataSource.name?.toLowerCase() || "";
    const sourceType = dataSource.source_type?.toLowerCase() || "";

    return (
      name.includes(searchQuery.toLowerCase()) ||
      sourceType.includes(searchQuery.toLowerCase())
    );
  });

  const handleDeleteClick = (dataSource: DataSource) => {
    setDataSourceToDelete(dataSource);
    setIsDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!dataSourceToDelete?.id || !onDeleteDataSource) return;

    try {
      setIsDeleting(true);
      await onDeleteDataSource(dataSourceToDelete.id);
      toast.success("Data source deleted successfully.");
    } catch (error) {
      toast.error("Failed to delete data source.");
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
      setDataSourceToDelete(null);
    }
  };

  const getConnectionBadge = (dataSource: DataSource) => {
    const status = ['gmail', 'o365'].includes(dataSource.source_type)
      ? dataSource.connection_data.user_email !== undefined
        ? 'Connected'
        : 'Error'
      : (dataSource.connection_status?.status ?? 'Untested');

    if (status === "Connected") {
      return (
        <Badge variant="success">
          <CheckCircle className="w-3 h-3 mr-1" />
          Connected
        </Badge>
      );
    }

    if (status === "Error") {
      return (
        <Badge variant="destructive">
          <AlertCircle className="w-3 h-3 mr-1" />
          Error
        </Badge>
      );
    }

    return (
      <Badge variant="outline">
        <HelpCircle className="w-3 h-3 mr-1" />
        Untested
      </Badge>
    );
  };

  const columns: Column<DataSource>[] = [
    {
      header: "Name",
      key: "name",
      cell: (dataSource) => dataSource.name,
      className: "font-medium break-all",
    },
    {
      header: "Source Type",
      key: "source_type",
      cell: (dataSource) => dataSource.source_type,
      className: "truncate",
    },
    {
      header: "Status",
      key: "status",
      className: "overflow-hidden whitespace-nowrap text-clip",
      cell: (dataSource) => (
        <Badge variant={dataSource.is_active ? "default" : "secondary"}>
          {dataSource.is_active ? "Active" : "Inactive"}
        </Badge>
      ),
    },
    {
      header: "Connection",
      key: "connection",
      className: "overflow-hidden whitespace-nowrap text-clip",
      cell: (dataSource) => getConnectionBadge(dataSource),
    },
    {
      header: "Action",
      key: "action",
      cell: (dataSource) => (
        <ActionButtons
          onEdit={() => onEditDataSource?.(dataSource)}
          onDelete={() => handleDeleteClick(dataSource)}
          editTitle="Edit Data Source"
          deleteTitle="Delete Data Source"
        />
      ),
    },
  ];

  return (
    <>
      <DataTable
        data={filteredDataSources}
        columns={columns}
        loading={loading}
        error={error}
        searchQuery={searchQuery}
        pageSize={LIST_PAGE_SIZE}
        emptyMessage="No data sources found"
        notFoundMessage="No data sources found matching your search"
      />

      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDeleteConfirm}
        isInProgress={isDeleting}
        itemName={dataSourceToDelete?.name || ""}
        description={`This action cannot be undone. This will permanently delete the data source "${dataSourceToDelete?.name}".`}
      />
    </>
  );
}
