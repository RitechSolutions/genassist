import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-hot-toast';
import {
  getKnowledgeItemsList,
  deleteKnowledgeItem,
} from '@/services/api';
import { Button } from '@/components/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/select';
import {
  Database,
  Pencil,
  AlertCircle,
  Plus,
  FileText,
  Trash2,
  RefreshCw,
} from 'lucide-react';
import { SearchInput } from '@/components/SearchInput';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { KBListItem, FileItem } from '../types/knowledgeBase';

const DEFAULT_PAGE_SIZE = 20;

const KB_TYPE_OPTIONS = [
  { value: 'all', label: '(Show all)' },
  { value: 'text', label: 'Text' },
  { value: 'file', label: 'Files' },
  { value: 'url', label: 'URLs' },
  { value: 's3', label: 'S3' },
  { value: 'sharepoint', label: 'Sharepoint' },
  { value: 'smb_share_folder', label: 'Network Share/Folder' },
  { value: 'azure_blob', label: 'Azure Blob Storage' },
  { value: 'google_bucket', label: 'Google Bucket Storage' },
  { value: 'zendesk', label: 'Zendesk' },
] as const;

const KnowledgeBaseManager: React.FC = () => {
  const navigate = useNavigate();
  const [items, setItems] = useState<KBListItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadingMore, setLoadingMore] = useState<boolean>(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [knowledgeBaseToDelete, setKnowledgeBaseToDelete] = useState<Partial<KBListItem> | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const sentinelRef = useRef<HTMLDivElement>(null);

  const fetchItems = useCallback(async (currentPage: number, append: boolean = false) => {
    try {
      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
      }
      const response = await getKnowledgeItemsList(currentPage, DEFAULT_PAGE_SIZE);
      if (append) {
        setItems((prev) => [...prev, ...response.items]);
      } else {
        setItems(response.items);
      }
      setPage(response.page);
      setHasMore(response.page < response.total_pages);
      setError(null);
    } catch {
      setError('Failed to load knowledge base items');
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, []);

  const loadMore = useCallback(() => {
    if (!loadingMore && hasMore) {
      fetchItems(page + 1, true);
    }
  }, [loadingMore, hasMore, page, fetchItems]);

  useEffect(() => {
    fetchItems(1);
  }, [fetchItems]);

  // Infinite scroll
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loadingMore && !loading) {
          loadMore();
        }
      },
      { threshold: 0.1 }
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, loadingMore, loadMore, loading]);

  const handleDeleteClick = (id: string, name: string) => {
    setKnowledgeBaseToDelete({ id, name });
    setIsDeleteDialogOpen(true);
  };

  const handleDelete = async () => {
    if (!knowledgeBaseToDelete?.id) return;
    try {
      setIsDeleting(true);
      await deleteKnowledgeItem(knowledgeBaseToDelete.id);
      toast.success('Knowledge base deleted successfully.');
      setItems((prev) => prev.filter((s) => s.id !== knowledgeBaseToDelete.id));
    } catch {
      toast.error('Failed to delete knowledge base.');
    } finally {
      setKnowledgeBaseToDelete(null);
      setIsDeleteDialogOpen(false);
      setIsDeleting(false);
    }
  };

  const getFileDisplayName = (fileItem: string | FileItem): string => {
    if (typeof fileItem === 'string') {
      if (fileItem.startsWith('http://') || fileItem.startsWith('https://')) {
        try { return new URL(fileItem).pathname.split('/').pop() || fileItem; } catch { return fileItem; }
      }
      return fileItem.split('/').pop() || fileItem;
    }
    return fileItem.original_file_name || fileItem.file_path;
  };

  const filteredItems = items.filter((item) => {
    const matchesQuery =
      item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (item.description ?? '').toLowerCase().includes(searchQuery.toLowerCase());
    return matchesQuery && (item.type.toLowerCase() === typeFilter || typeFilter === 'all');
  });

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold">Knowledge Base</h2>
          <p className="text-zinc-400 font-normal">View and manage the knowledge base</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Select value={typeFilter} onValueChange={setTypeFilter} defaultValue="all">
              <SelectTrigger className="min-w-32 bg-white">
                <SelectValue placeholder="Filter by type" />
              </SelectTrigger>
              <SelectContent>
                {KB_TYPE_OPTIONS.map(({ value, label }) => (
                  <SelectItem key={value} value={value}>{label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <SearchInput
            placeholder="Search knowledge base..."
            className="min-w-64"
            value={searchQuery}
            onChange={setSearchQuery}
          />
          <Button onClick={() => navigate('/knowledge-base/new')} className="rounded-full">
            <Plus className="h-4 w-4 mr-2" />
            Add New
          </Button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 text-destructive bg-destructive/10 rounded-md">
          <AlertCircle className="h-4 w-4" />
          <p className="text-sm font-medium">{error}</p>
        </div>
      )}

      <div className="rounded-lg border bg-white overflow-hidden">
        {loading ? (
          <div className="flex justify-center items-center py-12">
            <div className="text-sm text-gray-500">Loading knowledge base items...</div>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 gap-4 text-center">
            <Database className="h-12 w-12 text-gray-400" />
            <h3 className="font-medium text-lg">No knowledge base items found</h3>
            <p className="text-sm text-gray-500 max-w-sm">
              {searchQuery ? 'Try adjusting your search query or ' : ''}add your first knowledge item to start building your knowledge base.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {filteredItems.map((item) => (
              <div key={item.id} className="py-4 px-6">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                  <div className="flex-1 flex flex-col space-y-1">
                    <div className="flex items-center gap-2">
                      <h4 className="text-lg font-semibold">{item.name}</h4>
                      <span className="inline-flex items-center rounded-md bg-gray-100 px-2 py-0.5 text-xs font-bold text-black">
                        {item.type.toUpperCase()}
                      </span>
                    </div>
                    <p className="text-sm text-gray-500">{item.description}</p>
                    {item.type === 'file' && (
                      <div className="flex items-center text-sm text-gray-500 mt-1">
                        <FileText className="h-4 w-4 mr-1" />
                        <span>
                          {item.files && item.files.length > 0
                            ? item.files.length === 1
                              ? getFileDisplayName(item.files[0])
                              : `${item.files.length} files`
                            : item.content?.replace('File: ', '').replace('Files: ', '')}
                        </span>
                      </div>
                    )}
                    {item.type === 'text' && item.content && (
                      <p className="text-sm text-gray-500 mt-1 line-clamp-1">
                        {item.content.substring(0, 100)}
                        {item.content.length > 100 ? '...' : ''}
                      </p>
                    )}
                    {item.type === 'url' && item.urls && item.urls.length > 0 && (
                      <div className="text-sm text-gray-500 mt-1">
                        {item.urls.length === 1 ? (
                          <div className="flex items-center">
                            <span>URL: </span>
                            <a href={item.urls[0]} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800 underline ml-1 truncate">
                              {item.urls[0]}
                            </a>
                          </div>
                        ) : (
                          <div className="flex items-center">
                            <span>{item.urls.length} URLs</span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="flex gap-2 justify-center md:justify-end w-full md:w-auto">
                    <Button variant="ghost" size="icon" onClick={() => navigate(`/knowledge-base/edit/${item.id}`)} className="h-8 w-8">
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => handleDeleteClick(item.id, item.name)} className="h-8 w-8 text-red-500">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            ))}
            {loadingMore && (
              <div className="flex items-center justify-center py-4 border-t">
                <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
                <span className="ml-2 text-sm text-muted-foreground">Loading more...</span>
              </div>
            )}
            <div ref={sentinelRef} className="h-1" />
          </div>
        )}
      </div>

      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDelete}
        isInProgress={isDeleting}
        itemName={knowledgeBaseToDelete?.name || ''}
        description={`This action cannot be undone. This will permanently delete knowledge base item "${knowledgeBaseToDelete?.name}".`}
      />
    </div>
  );
};

export default KnowledgeBaseManager;
