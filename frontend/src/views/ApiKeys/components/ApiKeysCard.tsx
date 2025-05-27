import { useEffect, useState } from "react";
import { ApiKey } from "@/interfaces/api-key.interface";
import { getAllApiKeys, revokeApiKey } from "@/services/apiKeys";
import { getAllUsers } from "@/services/users";
import { Card } from "@/components/card";
import { Badge } from "@/components/badge";
import { Loader2, Edit } from "lucide-react";
import { toast } from "react-hot-toast";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/table";
import { Button } from "@/components/button";
import { formatDate } from "@/helpers/utils";
import { User } from "@/interfaces/user.interface";

interface ApiKeysCardProps {
  searchQuery: string;
  refreshKey?: number;
  onEditApiKey: (apiKey: ApiKey) => void;
}

export function ApiKeysCard({ searchQuery, refreshKey = 0, onEditApiKey }: ApiKeysCardProps) {
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [apiKeyToRevoke, setApiKeyToRevoke] = useState<ApiKey | null>(null);
  const [isRevokeDialogOpen, setIsRevokeDialogOpen] = useState(false);
  const [isRevoking, setIsRevoking] = useState(false);

  useEffect(() => {
    fetchData();
  }, [refreshKey]);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [keysData, usersData] = await Promise.all([
        getAllApiKeys(),
        getAllUsers()
      ]);
      setApiKeys(keysData);
      setUsers(usersData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch data");
      toast.error("Failed to fetch data");
    } finally {
      setLoading(false);
    }
  };

  const getUsernameById = (userId: string) => {
    const user = users.find(user => user.id === userId);
    return user ? user.username : 'Unknown User';
  };

  const filteredApiKeys = apiKeys.filter((apiKey) =>
    apiKey.name.toLowerCase().includes(searchQuery.toLowerCase())
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

  if (filteredApiKeys.length === 0) {
    return (
      <Card className="p-8">
        <div className="text-center text-muted-foreground">
          {searchQuery ? "No API keys found matching your search" : "No API keys found"}
        </div>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>API Key</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Roles</TableHead>
              <TableHead>Created</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredApiKeys.map((apiKey) => (
              <TableRow key={apiKey.id}>
                <TableCell className="font-medium">{apiKey.name}</TableCell>
                <TableCell>
                  <div className="flex items-center">
                    <span className="font-mono text-sm">
                      {apiKey.masked_value ?? 'Key not available'}
                    </span>
                  </div>
                </TableCell>
                <TableCell>
                  <Badge variant={apiKey.is_active === 1 ? "default" : "secondary"}>
                    {apiKey.is_active === 1 ? "Active" : "Revoked"}
                  </Badge>
                </TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {apiKey.roles && apiKey.roles.length > 0 ? (
                      apiKey.roles.map(role => (
                        <Badge key={role.id} variant="outline" className="text-xs">
                          {role.name}
                        </Badge>
                      ))
                    ) : (
                      <span className="text-muted-foreground text-xs">No roles</span>
                    )}
                  </div>
                </TableCell>
                <TableCell>{apiKey.created_at ? formatDate(apiKey.created_at) : 'No date'}</TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onEditApiKey(apiKey)}
                      title="Edit API Key"
                    >
                      <Edit className="w-4 h-4 text-black" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </>
  );
} 