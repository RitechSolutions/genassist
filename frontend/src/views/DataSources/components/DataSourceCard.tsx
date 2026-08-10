import { Column } from "@/components/ui/data-table";
import { EntityTableCard } from "@/components/EntityTableCard";
import { Badge } from "@/components/badge";
import { DataSource } from "@/interfaces/dataSource.interface";
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
  const getConnectionBadge = (dataSource: DataSource) => {
    const status = ["gmail", "o365"].includes(dataSource.source_type)
      ? dataSource.connection_data.user_email !== undefined
        ? "Connected"
        : "Error"
      : (dataSource.connection_status?.status ?? "Untested");

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
  ];

  return (
    <EntityTableCard<DataSource>
      entityName="data source"
      searchQuery={searchQuery}
      filterFn={(dataSource, query) => {
        const name = dataSource.name?.toLowerCase() || "";
        const sourceType = dataSource.source_type?.toLowerCase() || "";
        const q = query.toLowerCase();

        return name.includes(q) || sourceType.includes(q);
      }}
      data={dataSources}
      loading={loading}
      deleteFn={
        onDeleteDataSource
          ? (dataSource) => onDeleteDataSource(dataSource.id!)
          : undefined
      }
      getItemName={(dataSource) => dataSource.name}
      deleteDescription={(dataSource) =>
        `This action cannot be undone. This will permanently delete the data source "${dataSource.name}".`
      }
      emptyMessage="No data sources found"
      notFoundMessage="No data sources found matching your search"
      columns={columns}
      rowActions={{
        header: "Action",
        key: "action",
        onEdit: (dataSource) => onEditDataSource?.(dataSource),
        editTitle: "Edit Data Source",
        deleteTitle: "Delete Data Source",
      }}
    />
  );
}
