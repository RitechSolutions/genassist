import { useState } from "react";
import { DataTable } from "@/components/DataTable";
import { ActionButtons } from "@/components/ActionButtons";
import { DeleteConfirmDialog } from "@/components/DeleteConfirmDialog";
import { TableCell, TableRow } from "@/components/table";
import { Badge } from "@/components/badge";
import { DataSource } from "@/interfaces/dataSource.interface";
import { toast } from "react-hot-toast";

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
  const [dataSourceToDelete, setDataSourceToDelete] = useState<DataSource | null>(null);
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
      toast.success("Data source deleted successfully");
    } catch (error) {
      toast.error("Failed to delete data source");
      console.error("Error deleting data source:", error);
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
      setDataSourceToDelete(null);
    }
  };

  const headers = ["Name", "Source Type", "Status", "Action"];

  const renderRow = (dataSource: DataSource) => (
    <TableRow key={dataSource.id}>
      <TableCell className="font-medium">{dataSource.name}</TableCell>
      <TableCell>{dataSource.source_type}</TableCell>
      <TableCell className="text-center">
        <Badge variant={dataSource.is_active ? "default" : "secondary"}>
          {dataSource.is_active ? "Active" : "Inactive"}
        </Badge>
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

      <DeleteConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDeleteConfirm}
        isDeleting={isDeleting}
        itemName={dataSourceToDelete?.name || ""}
        description={`This action cannot be undone. This will permanently delete the data source "${dataSourceToDelete?.name}".`}
      />
    </>
  );
}
