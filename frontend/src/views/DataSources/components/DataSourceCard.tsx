import { useState } from "react";
import { DataTable } from "@/components/DataTable";
import { ActionButtons } from "@/components/ActionButtons";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { TableCell, TableRow } from "@/components/table";
import { Badge } from "@/components/badge";
import { DataSource } from "@/interfaces/dataSource.interface";
import { toast } from "react-hot-toast";
import { CheckCircle, AlertCircle, HelpCircle } from "lucide-react";

interface DataSourceCardProps {
  dataSources: DataSource[];
  searchQuery: string;
  refreshKey: number;
  onEditDataSource?: (dataSource: DataSource) => void;
  onDeleteDataSource?: (id: string) => Promise<void>;
}

export function DataSourceCard({
  searchQuery,
  dataSources,
  onEditDataSource,
  onDeleteDataSource,
}: DataSourceCardProps) {
  const [loading, setLoading] = useState(false);
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

  const headers = ["Name", "Source Type", "Status", "Connection", "Action"];

  const getConnectionBadge = (dataSource: DataSource) => {
    if (["gmail", "o365"].includes(dataSource.source_type)) {
      if (dataSource.connection_data.user_email !== undefined) {
        return (
          <Badge variant="success">
            <CheckCircle className="w-3 h-3 mr-1" />
            Connected
          </Badge>
        );
      }
      return (
        <Badge variant="outline">
          <AlertCircle className="w-3 h-3 mr-1" />
          Not Connected
        </Badge>
      );
    }

    const status = dataSource.connection_status?.status ?? "Untested";

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

  const renderRow = (dataSource: DataSource) => (
    <TableRow key={dataSource.id}>
      <TableCell className="font-medium break-all">{dataSource.name}</TableCell>
      <TableCell className="truncate">{dataSource.source_type}</TableCell>
      <TableCell className="overflow-hidden whitespace-nowrap text-clip">
        <Badge variant={dataSource.is_active ? "default" : "secondary"}>
          {dataSource.is_active ? "Active" : "Inactive"}
        </Badge>
      </TableCell>
      <TableCell className="overflow-hidden whitespace-nowrap text-clip">
        {getConnectionBadge(dataSource)}
        {["gmail", "o365"].includes(dataSource.source_type) &&
          dataSource.oauth_email && (
            <div className="text-xs text-gray-500 mt-1">
              {dataSource.oauth_email}
            </div>
          )}
      </TableCell>
      <TableCell>
        <ActionButtons
          onEdit={() => onEditDataSource?.(dataSource)}
          onDelete={() => handleDeleteClick(dataSource)}
          editTitle="Edit Data Source"
          deleteTitle="Delete Data Source"
        />
      </TableCell>
    </TableRow>
  );

  return (
    <>
      <DataTable
        data={filteredDataSources}
        loading={loading}
        error={error}
        searchQuery={searchQuery}
        headers={headers}
        renderRow={renderRow}
        emptyMessage="No data sources found"
        searchEmptyMessage="No data sources found matching your search"
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
