import { useEffect, useState } from 'react';
import { DataTable, Column } from '@/components/ui/data-table';
import { LIST_PAGE_SIZE } from '@/constants/pagination';
import { Button } from '@/components/button';
import { Badge } from '@/components/badge';
import { Pencil, RefreshCw, Trash } from 'lucide-react';
import { ApiKeyExpiryLines } from '@/components/api-keys/ApiKeyExpiryLines';
import { RotateApiKeyDialog, type RotateApiKeyTarget } from '@/components/api-keys/RotateApiKeyDialog';
import { ApiKey } from '@/interfaces/api-key.interface';
import { getAllApiKeys } from '@/services/apiKeys';
import { getAllUsers } from '@/services/users';
import { toast } from 'react-hot-toast';
import { formatDate } from '@/helpers/utils';
import { User } from '@/interfaces/user.interface';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/RadixTooltip';
import { TooltipButton } from '@/components/tooltip-button';

interface ApiKeysCardProps {
  searchQuery: string;
  refreshKey?: number;
  onEditApiKey: (apiKey: ApiKey) => void;
  updatedApiKey?: ApiKey | null;
  onApiKeyRotated?: (apiKey: ApiKey) => void;
  onDeleteApiKey: (apiKey: ApiKey) => void;
}

export function ApiKeysCard({
  searchQuery,
  refreshKey = 0,
  onEditApiKey,
  updatedApiKey = null,
  onApiKeyRotated,
  onDeleteApiKey,
}: ApiKeysCardProps) {
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rotateTarget, setRotateTarget] = useState<RotateApiKeyTarget | null>(null);

  useEffect(() => {
    fetchData();
  }, [refreshKey]);

  useEffect(() => {
    if (updatedApiKey) {
      setApiKeys((prevKeys) => prevKeys.map((key) => (key.id === updatedApiKey.id ? updatedApiKey : key)));
    }
  }, [updatedApiKey]);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [keysData, usersData] = await Promise.all([getAllApiKeys(), getAllUsers()]);
      setApiKeys(keysData);
      setUsers(usersData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data');
      toast.error('Failed to fetch data.');
    } finally {
      setLoading(false);
    }
  };

  const filteredApiKeys = apiKeys.filter((apiKey) => apiKey.name.toLowerCase().includes(searchQuery.toLowerCase()));

  const columns: Column<ApiKey>[] = [
    {
      header: 'Name',
      key: 'name',
      cell: (apiKey) => apiKey.name,
      className: 'font-medium break-all',
    },
    {
      header: 'Roles',
      key: 'roles',
      className: 'overflow-hidden whitespace-nowrap text-clip',
      cell: (apiKey) => (
        <div className="flex flex-wrap gap-1">
          {apiKey.roles && apiKey.roles.length > 0 ? (
            apiKey.roles.map((role) => (
              <Badge key={role.id} variant="outline" className="text-xs">
                {role.name}
              </Badge>
            ))
          ) : (
            <span className="text-muted-foreground text-xs">No roles</span>
          )}
        </div>
      ),
    },
    {
      header: 'Created',
      key: 'created_at',
      className: 'truncate',
      cell: (apiKey) => (apiKey.created_at ? formatDate(apiKey.created_at) : 'No date'),
    },
    {
      header: 'Status',
      key: 'status',
      className: 'overflow-hidden whitespace-nowrap text-clip',
      cell: (apiKey) => (
        <Badge variant={apiKey.is_active === 1 ? 'default' : 'secondary'}>
          {apiKey.is_active === 1 ? 'Active' : 'Revoked'}
        </Badge>
      ),
    },
    {
      header: 'Validity',
      key: 'validity',
      className: 'max-w-[220px]',
      cell: (apiKey) => <ApiKeyExpiryLines apiKey={apiKey} />,
    },
    {
      header: 'Actions',
      key: 'actions',
      className: 'space-x-1',
      cell: (apiKey) => (
        <>
          <TooltipButton
            button={
              <Button variant="ghost" size="sm" onClick={() => setRotateTarget({ key: apiKey, overlap: '0' })}>
                <RefreshCw className="w-4 h-4 text-foreground" />
              </Button>
            }
            tooltipContent={{ side: 'top', align: 'center', children: <p>Rotate secret</p> }}
          />
          <TooltipButton
            button={<Button variant="ghost" size="sm" onClick={() => onEditApiKey(apiKey)} title="Edit API Key">
              <Pencil className="w-4 h-4 text-foreground" />
            </Button>}
            tooltipContent={{ side: 'top', align: 'center', children: <p>Edit API Key</p> }}
          />
          <TooltipButton
            button={<Button variant="ghost" size="sm" onClick={() => onDeleteApiKey(apiKey)} title="Delete API Key">
              <Trash className="w-4 h-4 text-destructive" />
            </Button>}
            tooltipContent={{ side: 'top', align: 'center', children: <p>Delete API Key</p> }}
          />
        </>
      ),
    },
  ];

  return (
    <>
      <DataTable
        data={filteredApiKeys}
        columns={columns}
        loading={loading}
        error={error}
        searchQuery={searchQuery}
        pageSize={LIST_PAGE_SIZE}
        emptyMessage="No API keys found"
        notFoundMessage="No API keys found matching your search"
      />
      <RotateApiKeyDialog
        open={rotateTarget !== null}
        target={rotateTarget}
        onOpenChange={(open) => {
          if (!open) setRotateTarget(null);
        }}
        onRotated={(saved) => {
          setApiKeys((rows) => rows.map((x) => (x.id === saved.id ? saved : x)));
          onApiKeyRotated?.(saved);
          setRotateTarget(null);
        }}
      />
    </>
  );
}
