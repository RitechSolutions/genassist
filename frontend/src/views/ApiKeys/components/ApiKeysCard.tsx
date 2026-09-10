import { useCallback, useEffect, useRef, useState } from 'react';
import { DataTable, Column } from '@/components/ui/data-table';
import { PaginationBar } from '@/components/PaginationBar';
import { LIST_PAGE_SIZE } from '@/constants/pagination';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';
import { Button } from '@/components/button';
import { Badge } from '@/components/badge';
import { KeyRound, Pencil, RefreshCw, Trash } from 'lucide-react';
import { ListEmptyState } from '@/components/ListEmptyState';
import { ApiKeyExpiryLines } from '@/components/api-keys/ApiKeyExpiryLines';
import { RotateApiKeyDialog, type RotateApiKeyTarget } from '@/components/api-keys/RotateApiKeyDialog';
import { ApiKey } from '@/interfaces/api-key.interface';
import { getApiKeysPaginated } from '@/services/apiKeys';
import { toast } from 'react-hot-toast';
import { formatDate } from '@/helpers/utils';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/RadixTooltip';
import { TooltipButton } from '@/components/tooltip-button';

const SEARCH_DEBOUNCE_MS = 300;

interface ApiKeysCardProps {
  searchQuery: string;
  refreshKey?: number;
  onCreateApiKey?: () => void;
  onEditApiKey: (apiKey: ApiKey) => void;
  updatedApiKey?: ApiKey | null;
  onApiKeyRotated?: (apiKey: ApiKey) => void;
  onDeleteApiKey: (apiKey: ApiKey) => void;
}

export function ApiKeysCard({
  searchQuery,
  refreshKey = 0,
  onCreateApiKey,
  onEditApiKey,
  updatedApiKey = null,
  onApiKeyRotated,
  onDeleteApiKey,
}: ApiKeysCardProps) {
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rotateTarget, setRotateTarget] = useState<RotateApiKeyTarget | null>(null);

  const debouncedSearch = useDebouncedValue(searchQuery, SEARCH_DEBOUNCE_MS).trim();
  const requestSeqRef = useRef(0);
  const lastResetSigRef = useRef(`${debouncedSearch}|${refreshKey}`);

  const fetchData = useCallback(async () => {
    const seq = ++requestSeqRef.current;

    const resetSig = `${debouncedSearch}|${refreshKey}`;
    if (resetSig !== lastResetSigRef.current) {
      lastResetSigRef.current = resetSig;
      // A new search or a create/edit/delete refresh belongs on page 1
      if (page !== 1) {
        setPage(1);
        return;
      }
    }

    setLoading(true);
    setError(null);
    try {
      const data = await getApiKeysPaginated(page, LIST_PAGE_SIZE, debouncedSearch);
      if (seq !== requestSeqRef.current) return;

      // Rows removed elsewhere can leave the page past the end: fall back to the last valid page
      const lastPage = Math.max(1, data.total_pages);
      if (data.items.length === 0 && page > lastPage) {
        setPage(lastPage);
        return;
      }

      setApiKeys(data.items);
      setTotal(data.total);
    } catch (err) {
      if (seq !== requestSeqRef.current) return;
      setError(err instanceof Error ? err.message : 'Failed to fetch data');
      toast.error('Failed to fetch data.');
    } finally {
      if (seq === requestSeqRef.current) setLoading(false);
    }
  }, [page, debouncedSearch, refreshKey]);

  useEffect(() => {
    fetchData();
    return () => {
      requestSeqRef.current += 1;
    };
  }, [fetchData]);

  useEffect(() => {
    if (updatedApiKey) {
      setApiKeys((prevKeys) => prevKeys.map((key) => (key.id === updatedApiKey.id ? updatedApiKey : key)));
    }
  }, [updatedApiKey]);

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
        data={apiKeys}
        columns={columns}
        loading={loading}
        error={error}
        onRetry={fetchData}
        searchQuery={debouncedSearch}
        emptyState={
          <ListEmptyState
            icon={<KeyRound className="h-12 w-12 text-muted-foreground" />}
            title={debouncedSearch ? "No matching API keys" : "No API keys yet"}
            description={
              debouncedSearch
                ? "No API keys match your search. Try a different name."
                : "API keys let external services authenticate with the platform. Create one to grant programmatic access."
            }
            action={
              !debouncedSearch && onCreateApiKey ? (
                <Button className="rounded-full" onClick={onCreateApiKey}>
                  Generate your first API key
                </Button>
              ) : undefined
            }
          />
        }
      />
      {!loading && !error && (
        <PaginationBar
          total={total}
          currentPage={page}
          pageSize={LIST_PAGE_SIZE}
          pageItemCount={apiKeys.length}
          onPageChange={setPage}
        />
      )}
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
