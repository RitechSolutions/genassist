import { useEffect, useState } from "react";
import { DataTable } from "@/components/DataTable";
import { TableCell, TableRow } from "@/components/table";
import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import { Edit } from "lucide-react";
import { getAllUsers } from "@/services/users";
import { toast } from "react-hot-toast";
import { User } from "@/interfaces/user.interface";
import { getPaginationMeta } from "@/helpers/pagination";
import { PaginationBar } from "@/components/PaginationBar";

interface UsersCardProps {
  searchQuery: string;
  refreshKey?: number;
  onEditUser: (user: User) => void;
  updatedUser?: User | null;
}

export function UsersCard({
  searchQuery,
  refreshKey = 0,
  onEditUser,
  updatedUser = null,
}: UsersCardProps) {
  const PAGE_SIZE = 10;
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);

  useEffect(() => {
    const fetchUsers = async () => {
      setLoading(true);
      try {
        const userData = await getAllUsers();
        setUsers(userData);
        setError(null);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to fetch users";
        setError(message);
        toast.error(message);
      } finally {
        setLoading(false);
      }
    };

    fetchUsers();
  }, [refreshKey]);

  useEffect(() => {
    if (updatedUser) {
      setUsers((prevUsers) =>
        prevUsers.map((user) =>
          user.id === updatedUser.id ? updatedUser : user
        )
      );
    }
  }, [updatedUser]);

  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery]);

  const filteredUsers = users.filter(
    (user) =>
      user.username.toLowerCase().includes(searchQuery.toLowerCase()) ||
      user.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const pagination = getPaginationMeta(filteredUsers.length, PAGE_SIZE, currentPage);
  const paginatedUsers = filteredUsers.slice(pagination.startIndex, pagination.endIndex);
  const pageItemCount = paginatedUsers.length;

  const headers = [
    "ID",
    "Username",
    "Email",
    "Status",
    "User Type",
    "Roles",
    "Action",
  ];

  const renderRow = (user: User, index: number) => (
    <TableRow key={user.id}>
      <TableCell>{pagination.startIndex + index + 1}</TableCell>
      <TableCell className="font-medium break-all">{user.username}</TableCell>
      <TableCell className="truncate">{user.email}</TableCell>
      <TableCell className="overflow-hidden whitespace-nowrap text-clip">
        <Badge variant={user.is_active === 1 ? "default" : "secondary"}>
          {user.is_active === 1 ? "Active" : "Inactive"}
        </Badge>
      </TableCell>
      <TableCell className="truncate">
        {user.user_type?.name || "N/A"}
      </TableCell>
      <TableCell className="overflow-hidden whitespace-nowrap text-clip">
        <div className="flex gap-1 flex-wrap">
          {user.roles && user.roles.length > 0 ? (
            user.roles.map((role, index) => (
              <Badge key={index} variant="outline">
                {role.name}
              </Badge>
            ))
          ) : (
            <span className="text-gray-400">—</span>
          )}
        </div>
      </TableCell>
      <TableCell>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onEditUser(user)}
          title="Edit User"
        >
          <Edit className="w-4 h-4 text-black" />
        </Button>
      </TableCell>
    </TableRow>
  );

  return (
    <>
      <DataTable
        data={paginatedUsers}
        loading={loading}
        error={error}
        searchQuery={searchQuery}
        headers={headers}
        renderRow={renderRow}
        emptyMessage="No users found"
        searchEmptyMessage="No users found matching your search"
      />

      <PaginationBar
        total={pagination.total}
        pageSize={PAGE_SIZE}
        currentPage={pagination.safePage}
        pageItemCount={pageItemCount}
        onPageChange={setCurrentPage}
      />
    </>
  );
}
