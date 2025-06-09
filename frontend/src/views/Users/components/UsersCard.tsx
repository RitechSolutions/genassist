import { useEffect, useState } from "react";
import { DataTable } from "@/components/DataTable";
import { TableCell, TableRow } from "@/components/table";
import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import { Edit } from "lucide-react";
import { getAllUsers } from "@/services/users";
import { toast } from "react-hot-toast";
import { User } from "@/interfaces/user.interface";

interface UsersCardProps {
  searchQuery: string;
  refreshKey?: number;
  onEditUser: (user: User) => void;
}

export function UsersCard({ searchQuery, refreshKey = 0, onEditUser }: UsersCardProps) {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchUsers = async () => {
      setLoading(true);
      try {
        const userData = await getAllUsers();
        setUsers(userData);
        setError(null);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to fetch users";
        setError(message);
        toast.error(message);
        console.error("Error fetching data:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchUsers();
  }, [refreshKey]);

  const filteredUsers = users.filter((user) =>
    user.username.toLowerCase().includes(searchQuery.toLowerCase()) ||
    user.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const headers = ["ID", "Username", "Email", "Status", "User Type", "Roles", "Action"];

  const renderRow = (user: User, index: number) => (
    <TableRow key={user.id}>
      <TableCell>{index + 1}</TableCell>
      <TableCell className="font-medium">{user.username}</TableCell>
      <TableCell>{user.email}</TableCell>
      <TableCell>
        <Badge variant={user.is_active === 1 ? "default" : "secondary"}>
          {user.is_active === 1 ? "Active" : "Inactive"}
        </Badge>
      </TableCell>
      <TableCell>{user.user_type?.name || "N/A"}</TableCell>
      <TableCell>
        <div className="flex gap-1 flex-wrap">
          {user.roles && user.roles.length > 0 ? (
            user.roles.map((role, index) => (
              <Badge key={index} variant="outline">
                {role.name}
              </Badge>
            ))
          ) : (
            <span className="text-muted-foreground">-</span>
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
    <DataTable
      data={filteredUsers}
      loading={loading}
      error={error}
      searchQuery={searchQuery}
      headers={headers}
      renderRow={renderRow}
      emptyMessage="No users found"
      searchEmptyMessage="No users found matching your search"
    />
  );
}
