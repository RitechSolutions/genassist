import { useEffect, useState } from "react";
import { DataTable, Column } from "@/components/ui/data-table";
import { LIST_PAGE_SIZE } from "@/constants/pagination";
import { formatDate } from "@/helpers/utils";
import { UserType } from "@/interfaces/userType.interface";
import { toast } from "react-hot-toast";
import { getAllUserTypes } from "@/services/userTypes";

interface UserTypesCardProps {
  searchQuery: string;
  refreshKey?: number;
}

export function UserTypesCard({
  searchQuery,
  refreshKey = 0,
}: UserTypesCardProps) {
  const [userTypes, setUserTypes] = useState<UserType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchUserTypes();
  }, [refreshKey]);

  const fetchUserTypes = async () => {
    try {
      setLoading(true);
      const data = await getAllUserTypes();
      setUserTypes(data);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to fetch user types"
      );
      toast.error("Failed to fetch user types.");
    } finally {
      setLoading(false);
    }
  };

  const filteredUserTypes = userTypes.filter((userType) =>
    userType.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const columns: Column<UserType>[] = [
    { header: "ID", key: "id", cell: (_userType, index) => index + 1 },
    {
      header: "Name",
      key: "name",
      cell: (userType) => userType.name,
      className: "font-medium break-all",
    },
    {
      header: "Created At",
      key: "created_at",
      cell: (userType) => formatDate(userType.created_at),
      className: "truncate",
    },
    {
      header: "Updated At",
      key: "updated_at",
      cell: (userType) => formatDate(userType.updated_at),
      className: "truncate",
    },
  ];

  return (
    <DataTable
      data={filteredUserTypes}
      columns={columns}
      loading={loading}
      error={error}
      searchQuery={searchQuery}
      pageSize={LIST_PAGE_SIZE}
      emptyMessage="No user types found"
      notFoundMessage="No user types found matching your search"
    />
  );
}
