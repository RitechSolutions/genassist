import { Card } from "@/components/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/table";
import { Badge } from "@/components/badge";
import { useEffect, useState } from "react";
import { getAllUsers } from "@/services/users";
import { Edit, Loader2 } from "lucide-react";
import { toast } from "react-hot-toast";
import { Trash2 } from "lucide-react";
import { User } from "@/interfaces/user.interface";
import { Button } from "@/components/button";

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

  if (loading) {
    return (
      <Card className="p-8 flex justify-center items-center">
        <Loader2 className="w-6 h-6 animate-spin" />
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="p-8">
        <div className="text-center text-red-500">{error}</div>
      </Card>
    );
  }

  if (filteredUsers.length === 0) {
    return (
      <Card className="p-8">
        <div className="text-center text-muted-foreground">
          {searchQuery ? "No users found matching your search" : "No users found"}
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>ID</TableHead>
            <TableHead>Username</TableHead>
            <TableHead>Email</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>User Type</TableHead>
            <TableHead>Roles</TableHead>
            <TableHead>Action</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filteredUsers.map((user, index) => (
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
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}
