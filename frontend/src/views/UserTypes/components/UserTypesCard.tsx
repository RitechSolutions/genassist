import { useEffect, useState } from "react";
import { DataTable } from "@/components/DataTable";
import { TableCell, TableRow } from "@/components/table";
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

  const headers = ["ID", "Name", "Created At", "Updated At"];

  const renderRow = (userType: UserType, index: number) => (
    <TableRow key={userType.id}>
      <TableCell>{index + 1}</TableCell>
      <TableCell className="font-medium break-all">{userType.name}</TableCell>
      <TableCell className="truncate">
        {formatDate(userType.created_at)}
      </TableCell>
      <TableCell className="truncate">
        {formatDate(userType.updated_at)}
      </TableCell>
    </TableRow>
  );

  return (
    <>
      <DataTable
        data={filteredUserTypes}
        loading={loading}
        error={error}
        searchQuery={searchQuery}
        headers={headers}
        renderRow={renderRow}
        emptyMessage="No user types found"
        searchEmptyMessage="No user types found matching your search"
      />
    </>
  );
}
