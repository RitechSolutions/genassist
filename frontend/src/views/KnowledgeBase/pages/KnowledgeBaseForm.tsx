import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'react-hot-toast';
import {
  getKnowledgeItem,
  createKnowledgeItem,
  updateKnowledgeItem,
  uploadFiles as apiUploadFiles,
  executeKnowledgeBaseSyncronizationManually,
} from '@/services/api';
import { getApiUrlString } from '@/config/api';
import { getAllDataSources } from '@/services/dataSources';
import { getAllLLMAnalysts } from '@/services/llmAnalyst';
import { v4 as uuidv4 } from 'uuid';
import { Badge } from '@/components/badge';
import { Button } from '@/components/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/popover';
import { SimpleInput as Input } from '@/components/ui/simpleInput';
import { SimpleTextarea as Textarea } from '@/components/ui/simpleTextarea';
import { Switch } from '@/components/switch';
import { Label } from '@/components/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/select';
import { CreateNewSelectItem } from '@/components/CreateNewSelectItem';
import {
  FilePlus,
  Upload,
  Database,
  X,
  AlertCircle,
  CheckCircle2,
  Plus,
  ChevronLeft,
  Trash2,
  Download,
  RefreshCw,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/collapsible';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { RagConfigValues } from '../types/ragSchema';
import { LegacyRagConfig, DEFAULT_LEGACY_RAG_CONFIG } from '../utils/ragDefaults';
import DynamicRagConfigSection from '../components/DynamicRagConfigSection';
import { DataSourceDialog } from '@/views/DataSources/components/DataSourceDialog';
import { isEqual } from 'lodash';
import { KnowledgeItem, UrlHeaderRow, UploadResult, FileItem } from '../types/knowledgeBase';
import { SidebarProvider, SidebarTrigger } from '@/components/sidebar';
import { AppSidebar } from '@/layout/app-sidebar';
import { useIsMobile } from '@/hooks/useMobile';
import { Progress } from '@/components/progress';

const DEFAULT_FORM_DATA: KnowledgeItem = {
  id: uuidv4(),
  name: '',
  description: '',
  content: '',
  type: 'text',
  sync_source_id: null,
  llm_provider_id: null,
  files: [],
  urls: [],
  use_http_request: false,
  rag_config: DEFAULT_LEGACY_RAG_CONFIG,
  processing_filter: '',
  llm_analyst_id: null,
  processing_mode: null,
  transcription_engine: 'openai_whisper',
  save_in_conversation: false,
  save_output: false,
  save_output_path: '',
};

const KNOWN_HTTP_HEADERS = [
  'Authorization',
  'User-Agent',
  'Accept',
  'Accept-Language',
  'Content-Type',
  'Cache-Control',
  'If-None-Match',
  'If-Modified-Since',
];

const toPlainHeaders = (o: unknown): Record<string, string> =>
  o && typeof o === 'object' && !Array.isArray(o)
    ? Object.fromEntries(
        Object.entries(o).filter(([k, v]) => typeof k === 'string' && typeof v === 'string')
      )
    : {};

const targetTypes = {
  s3: 'S3',
  sharepoint: 'o365',
  smb_share_folder: 'smb_share_folder',
  azure_blob: 'azure_blob',
  google_bucket: 'gmail',
  zendesk: 'zendesk',
};

const acceptedFileTypes = [
  '.pdf', '.docx', '.doc', '.txt', '.csv', '.xls', '.xlsx',
  '.pptx', '.ppt', '.html', '.htm', '.yaml', '.yml', '.json', '.jsonl', '.md',
];

function syncStatusBadgeVariant(
  status: string
): 'default' | 'secondary' | 'destructive' | 'outline' | 'success' {
  const s = status.toLowerCase();
  if (s === 'error' || s.includes('fail')) return 'destructive';
  if (s.includes('warning')) return 'secondary';
  if (s === 'success') return 'success';
  return 'outline';
}

function isSyncErrorStatus(status: string | null | undefined): boolean {
  if (!status) return false;
  const s = status.toLowerCase();
  return s === 'error' || s.includes('fail');
}

const KnowledgeBaseForm: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id?: string }>();
  const isEditMode = Boolean(id);
  const isMobile = useIsMobile();

  const [editingItem, setEditingItem] = useState<KnowledgeItem | null>(null);
  const [formData, setFormData] = useState<KnowledgeItem>({ ...DEFAULT_FORM_DATA, id: uuidv4() });
  const [dynamicRagConfig, setDynamicRagConfig] = useState<RagConfigValues>({});
  const [loading, setLoading] = useState<boolean>(isEditMode);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [urls, setUrls] = useState<string[]>(['']);
  const [urlHeaders, setUrlHeaders] = useState<UrlHeaderRow[]>([]);
  const [availableSources, setAvailableSources] = useState([]);
  const [llmAnalysts, setLlmAnalysts] = useState([]);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isSyncSaveDialogOpen, setIsSyncSaveDialogOpen] = useState(false);
  const [isDataSourceDialogOpen, setIsDataSourceDialogOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const syncAfterSaveRef = useRef(false);

  // Load full item when in edit mode
  useEffect(() => {
    if (!id) return;
    const loadItem = async () => {
      try {
        setLoading(true);
        const item = (await getKnowledgeItem(id)) as KnowledgeItem;
        setEditingItem(item);
        setFormData({
          id: item.id,
          name: item.name,
          description: item.description,
          content: item.content,
          type: item.type || DEFAULT_FORM_DATA.type,
          sync_source_id: item.sync_source_id,
          use_http_request: (item.extra_metadata?.use_http_request as boolean | undefined) ?? false,
          llm_provider_id: item.llm_provider_id || DEFAULT_FORM_DATA.llm_provider_id,
          sync_schedule: item.sync_schedule || DEFAULT_FORM_DATA.sync_schedule,
          sync_active: (item.sync_active as boolean | undefined) ?? DEFAULT_FORM_DATA.sync_active,
          files: item.files || DEFAULT_FORM_DATA.files,
          rag_config: item.rag_config || DEFAULT_LEGACY_RAG_CONFIG,
          processing_filter: (item.extra_metadata?.processing_filter as string | undefined) ?? null,
          llm_analyst_id: (item.extra_metadata?.llm_analyst_id as string | null | undefined) ?? null,
          processing_mode: (item.extra_metadata?.processing_mode as string | null | undefined) ?? null,
          transcription_engine: (item.extra_metadata?.transcription_engine as string | undefined) ?? null,
          save_in_conversation: (item.extra_metadata?.save_in_conversation as boolean | undefined) ?? false,
          save_output: (item.extra_metadata?.save_output as boolean | undefined) ?? false,
          save_output_path: (item.extra_metadata?.save_output_path as string | undefined) ?? null,
          extra_metadata: item.extra_metadata || {},
        });

        const existingUrlHeaders = item.extra_metadata?.http_headers || item.extra_metadata?.custom_headers;
        if (existingUrlHeaders && typeof existingUrlHeaders === 'object') {
          const rows = Object.entries(existingUrlHeaders as Record<string, string>)
            .map(([key, value]) => ({
              id: uuidv4(),
              key,
              value: value ?? '',
              keyType: (KNOWN_HTTP_HEADERS.includes(key) ? 'known' : 'custom') as 'known' | 'custom',
            }))
            .filter((row) => row.key);
          setUrlHeaders(rows);
        }

        setDynamicRagConfig((item.rag_config || DEFAULT_LEGACY_RAG_CONFIG) as RagConfigValues);

        if ((item.type === 'url' || item.type === 'sharepoint') && item.urls && item.urls.length > 0) {
          setUrls(item.urls);
        }
      } catch {
        toast.error('Failed to load knowledge base item');
        navigate('/knowledge-base');
      } finally {
        setLoading(false);
      }
    };
    loadItem();
  }, [id, navigate]);

  // Load LLM analysts
  useEffect(() => {
    const fetchLLMAnalysts = async () => {
      try {
        const analysts = await getAllLLMAnalysts();
        setLlmAnalysts(analysts.filter((a) => a.is_active === 1));
      } catch {
        // ignore
      }
    };
    fetchLLMAnalysts();
  }, []);

  // Load data sources when type changes
  const fetchSources = useCallback(async () => {
    if (formData.type && formData.type in targetTypes) {
      const allSources = await getAllDataSources();
      const targetType = targetTypes[formData.type as keyof typeof targetTypes];
      setAvailableSources(allSources.filter((s) => s.source_type.toLowerCase() === targetType.toLowerCase()));
    }
  }, [formData.type]);

  useEffect(() => {
    fetchSources();
  }, [fetchSources]);

  const getComparableState = useCallback(() => {
    const currentUrls =
      formData.type === 'url' || formData.type === 'sharepoint'
        ? urls.filter((u) => u.trim() !== '')
        : [];
    const currentHeaders = urlHeaders.reduce<Record<string, string>>((acc, h) => {
      if (h.key.trim()) acc[h.key] = h.value;
      return acc;
    }, {});
    const norm = (v: unknown) => (v === 'none' || v == null ? null : v);
    return {
      name: formData.name, description: formData.description, content: formData.content,
      type: formData.type, sync_source_id: formData.sync_source_id ?? null,
      sync_schedule: formData.sync_schedule ?? null, sync_active: Boolean(formData.sync_active),
      urls: currentUrls, http_headers: toPlainHeaders(currentHeaders),
      use_http_request: Boolean(formData.use_http_request),
      processing_filter: formData.processing_filter ?? null,
      llm_analyst_id: norm(formData.llm_analyst_id),
      processing_mode: norm(formData.processing_mode),
      transcription_engine: formData.transcription_engine ?? null,
      save_in_conversation: Boolean(formData.save_in_conversation),
      save_output: Boolean(formData.save_output),
      save_output_path: formData.save_output_path ?? null,
      allow_unpublished_articles: formData.type === 'zendesk' ? Boolean(formData.extra_metadata?.allow_unpublished_articles) : undefined,
      allow_html_content: formData.type === 'zendesk' ? Boolean(formData.extra_metadata?.allow_html_content) : undefined,
      rag_config: formData.rag_config ?? {},
      filePaths: formData.type === 'file'
        ? (formData.files || []).map((f) => typeof f === 'string' ? f : (f as FileItem).file_path)
        : [],
      hasNewFiles: selectedFiles.length > 0,
    };
  }, [formData, urls, urlHeaders, selectedFiles]);

  const getComparableOriginal = useCallback((orig: KnowledgeItem) => {
    const em = orig.extra_metadata || {};
    const norm = (v: unknown) => (v === 'none' || v == null ? null : v);
    return {
      name: orig.name, description: orig.description, content: orig.content,
      type: orig.type, sync_source_id: orig.sync_source_id ?? null,
      sync_schedule: orig.sync_schedule ?? null, sync_active: Boolean(orig.sync_active),
      urls: orig.urls || [], http_headers: toPlainHeaders(em.http_headers || em.custom_headers),
      use_http_request: Boolean(em.use_http_request),
      processing_filter: (em.processing_filter as string) ?? null,
      llm_analyst_id: norm(em.llm_analyst_id), processing_mode: norm(em.processing_mode),
      transcription_engine: (em.transcription_engine as string) ?? null,
      save_in_conversation: Boolean(em.save_in_conversation),
      save_output: Boolean(em.save_output),
      save_output_path: (em.save_output_path as string) ?? null,
      allow_unpublished_articles: orig.type === 'zendesk' ? Boolean(em.allow_unpublished_articles) : undefined,
      allow_html_content: orig.type === 'zendesk' ? Boolean(em.allow_html_content) : undefined,
      rag_config: orig.rag_config ?? {},
      filePaths: (orig.files || []).map((f) => typeof f === 'string' ? f : (f as FileItem).file_path),
      hasNewFiles: false,
    };
  }, []);

  const hasSettingsChanged = useCallback(() => {
    if (!editingItem) return true;
    const original = getComparableOriginal(editingItem);
    return !isEqual(getComparableState(), original);
  }, [editingItem, getComparableState, getComparableOriginal]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleUrlChange = (index: number, value: string) => {
    setUrls((prev) => { const u = [...prev]; u[index] = value; return u; });
  };

  const addUrl = () => setUrls((prev) => [...prev, '']);
  const removeUrl = (index: number) => setUrls((prev) => prev.filter((_, i) => i !== index));

  const handleRagConfigChange = (updatedRagConfig: RagConfigValues) => {
    setDynamicRagConfig(updatedRagConfig);
    const ragConfig = updatedRagConfig as LegacyRagConfig;
    ragConfig.enabled = Object.keys(updatedRagConfig).some((k) => updatedRagConfig[k].enabled);
    setFormData((prev) => ({ ...prev, rag_config: ragConfig }));
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files ? Array.from(e.target.files) : [];
    setSelectedFiles([...files]);
    setFormData((prev) => ({
      ...prev,
      content: files.length > 0 ? `Files: ${files.map((f) => f.name).join(', ')}` : '',
    }));
  };

  const uploadFiles = async (): Promise<UploadResult[] | null> => {
    if (selectedFiles.length === 0) return null;
    setIsUploading(true);
    setUploadProgress(0);
    try {
      const result = await apiUploadFiles(selectedFiles, {
        onProgress: (pct) => setUploadProgress(pct),
      });
      return result as unknown as UploadResult[];
    } catch (err) {
      setError(`Failed to upload files: ${err instanceof Error ? err.message : String(err)}`);
      return null;
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  };

  const isValidCron = (cron: string): boolean => {
    const cronRegex =
      /^(((\*|\d+)(-\d+)?)(\/\d+)?)(,((\*|\d+)(-\d+)?)(\/\d+)?)*\s+(((\*|\d+)(-\d+)?)(\/\d+)?)(,((\*|\d+)(-\d+)?)(\/\d+)?)*\s+(((\*|\d+)(-\d+)?)(\/\d+)?)(,((\*|\d+)(-\d+)?)(\/\d+)?)*\s+(((\*|\d+)(-\d+)?)(\/\d+)?)(,((\*|\d+)(-\d+)?)(\/\d+)?)*\s+(((\*|\d+)(-\d+)?)(\/\d+)?)(,((\*|\d+)(-\d+)?)(\/\d+)?)*$/;
    return cronRegex.test(cron.trim());
  };

  const maskFileName = (fileName: string): string => {
    const maxLength = 100;
    if (fileName.length > maxLength) {
      return fileName.substring(0, maxLength / 2 - 10) + '......' + fileName.substring(fileName.length - (maxLength / 2 - 10));
    }
    return fileName;
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

  const getFileUrl = (fileItem: string | FileItem): string => {
    const addTenantId = (url: string): string => {
      const tenantId = localStorage.getItem('tenant_id');
      return tenantId && url.includes('file-manager') ? `${url}?X-Tenant-Id=${tenantId}` : url;
    };
    if (typeof fileItem === 'string') return addTenantId(fileItem);
    if (fileItem.file_id) {
      return addTenantId(new URL(`file-manager/files/${fileItem.file_id}/source`, getApiUrlString).toString());
    }
    return addTenantId(fileItem.url ?? (fileItem as { urls?: string }).urls ?? null);
  };

  const performSync = async () => {
    if (!editingItem?.id) return;
    let syncApiReturned = false;
    try {
      setIsSyncing(true);
      const data = (await executeKnowledgeBaseSyncronizationManually(editingItem.id)) as {
        status?: string;
        message?: string;
        zendesk_sync_results?: Array<{
          result?: {
            status?: string;
            error?: string;
            message?: string;
            articles_added?: number;
            articles_updated?: number;
            articles_deleted?: number;
            per_kb?: Array<{ status?: string; reason?: string; error?: string; note?: string }>;
          };
        }>;
      };
      syncApiReturned = true;
      if (data.status === 'error') {
        toast.error(data.message ?? 'Synchronization failed.');
        return;
      }
      const z = data.zendesk_sync_results?.[0]?.result;
      if (z?.status === 'failed') {
        toast.error(z.error ?? z.message ?? 'Zendesk sync failed.');
        return;
      }
      const firstKb = z?.per_kb?.[0];
      if (firstKb?.status === 'skipped') {
        toast.error(
          `Sync skipped: ${firstKb.reason ?? 'unknown'}. Check schedule, datasource, or Zendesk connection.`
        );
        return;
      }
      if (firstKb?.status === 'error') {
        console.error(firstKb?.error ?? 'Unknown error');
        toast.error('Zendesk sync error. See knowledge base sync status.');
        return;
      }
      if (z != null && (z.articles_added != null || z.articles_updated != null || z.articles_deleted != null)) {
        toast.success(
          `Sync completed: ${z.articles_added ?? 0} added, ${z.articles_updated ?? 0} updated, ${z.articles_deleted ?? 0} removed.`
        );
      } else {
        toast.success('Synchronization completed successfully.');
      }
    } catch {
      toast.error('Failed to trigger synchronization.');
    } finally {
      setIsSyncing(false);
      if (syncApiReturned && id) {
        try {
          setEditingItem((await getKnowledgeItem(id)) as KnowledgeItem);
        } catch {
          /* ignore refresh failure */
        }
      }
    }
  };

  const handleSyncNow = async () => {
    if (!editingItem?.id) { toast.error('Please save the knowledge base before syncing.'); return; }
    if (hasSettingsChanged()) { setIsSyncSaveDialogOpen(true); return; }
    await performSync();
  };

  const handleSaveAndSync = async () => {
    syncAfterSaveRef.current = true;
    setIsSyncSaveDialogOpen(false);
    formRef.current?.requestSubmit();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const requiredFields = [
      { label: 'name', isEmpty: !formData.name },
      { label: 'description', isEmpty: !formData.description },
    ];

    if (formData.type === 'text') requiredFields.push({ label: 'content', isEmpty: !formData.content });
    if (formData.type === 'file') {
      requiredFields.push({ label: 'files', isEmpty: selectedFiles.length === 0 && (!formData.files || formData.files.length === 0) });
    }
    if (formData.type === 's3') requiredFields.push({ label: 'source', isEmpty: !formData.sync_source_id });
    if (formData.type === 'zendesk') {
      requiredFields.push({ label: 'source', isEmpty: !formData.sync_source_id });
      if (formData.sync_active) requiredFields.push({ label: 'sync schedule', isEmpty: !formData.sync_schedule });
    }
    if (['s3', 'azure_blob'].includes(formData.type) && formData.sync_active) {
      requiredFields.push({ label: 'sync schedule', isEmpty: !formData.sync_schedule });
    }
    if (formData.type === 'url') {
      const hasValidUrl = urls.some((url) => url.trim() !== '');
      requiredFields.push({ label: 'urls', isEmpty: !hasValidUrl });
      urlHeaders.forEach((header) => {
        if (!header.key.trim() || !header.value.trim()) requiredFields.push({ label: 'custom header', isEmpty: true });
      });
    }
    if (formData.type === 'sharepoint') {
      const hasValidUrl = urls.some((url) => url.trim() !== '');
      requiredFields.push({ label: 'source', isEmpty: !formData.sync_source_id }, { label: 'url', isEmpty: !hasValidUrl });
      if (formData.sync_active) requiredFields.push({ label: 'sync schedule', isEmpty: !formData.sync_schedule });
    }
    if (formData.type === 'smb_share_folder') {
      requiredFields.push({ label: 'source', isEmpty: !formData.sync_source_id });
      if (formData.sync_active) requiredFields.push({ label: 'sync schedule', isEmpty: !formData.sync_schedule });
    }

    const missingFields = requiredFields
      .filter((f) => f.isEmpty)
      .map(({ label }) => label === 'url' ? 'URL' : label === 'urls' ? 'URLs' : label === 'files' ? 'Files' : label.charAt(0).toUpperCase() + label.slice(1));

    if (missingFields.length > 0) {
      if (missingFields.length === 1) {
        if (missingFields[0] === 'URLs') toast.error('At least one URL is required.');
        else if (missingFields[0] === 'Files') toast.error('At least one file is required.');
        else toast.error(`${missingFields[0]} is required.`);
      } else {
        toast.error(`Please provide: ${missingFields.join(', ')}.`);
      }
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setSuccess(null);

      if (['s3', 'sharepoint', 'smb_share_folder', 'azure_blob', 'zendesk'].includes(formData.type) && formData.sync_active && !isValidCron(formData.sync_schedule)) {
        throw new Error('Invalid cron expression. Expected format: * * * * *');
      }

      const dataToSubmit = { ...formData };

      const normalizedUrlHeaders = urlHeaders.reduce<Record<string, string>>((acc, header) => {
        const key = header.key.trim();
        if (!key) return acc;
        acc[key] = header.value;
        return acc;
      }, {});
      const hasUrlHeaders = Object.keys(normalizedUrlHeaders).length > 0;

      if (formData.type === 'zendesk') {
        dataToSubmit.extra_metadata = {
          ...(dataToSubmit.extra_metadata || {}),
          allow_unpublished_articles: dataToSubmit.extra_metadata?.allow_unpublished_articles || false,
          allow_html_content: dataToSubmit.extra_metadata?.allow_html_content || false,
        };
      }

      dataToSubmit.extra_metadata = {
        ...(dataToSubmit.extra_metadata || {}),
        use_http_request: dataToSubmit.use_http_request || false,
        http_headers: dataToSubmit.type === 'url' && hasUrlHeaders ? normalizedUrlHeaders : null,
        processing_filter: dataToSubmit.processing_filter || null,
        llm_analyst_id: dataToSubmit.llm_analyst_id || null,
        processing_mode: dataToSubmit.processing_mode || null,
        transcription_engine: dataToSubmit.processing_mode === 'transcribe' ? dataToSubmit.transcription_engine : null,
        save_in_conversation: dataToSubmit.processing_mode === 'transcribe' ? dataToSubmit.save_in_conversation : false,
        save_output: dataToSubmit.save_output || false,
        save_output_path: dataToSubmit.save_output && dataToSubmit.save_output_path ? dataToSubmit.save_output_path : null,
      };

      delete dataToSubmit.processing_filter;
      delete dataToSubmit.llm_analyst_id;
      delete dataToSubmit.processing_mode;
      delete dataToSubmit.transcription_engine;
      delete dataToSubmit.save_in_conversation;
      delete dataToSubmit.save_output;
      delete dataToSubmit.save_output_path;
      delete dataToSubmit.use_http_request;

      if (formData.type === 'url' || formData.type === 'sharepoint') {
        dataToSubmit.urls = urls.filter((url) => url.trim() !== '');
      } else {
        dataToSubmit.urls = [];
      }

      if (formData.type === 'file') {
        dataToSubmit.file_type = 'files';
        if (!dataToSubmit.files) dataToSubmit.files = [];

        if (selectedFiles.length > 0) {
          const uploadResults = await uploadFiles();
          if (!uploadResults || uploadResults.length === 0) throw new Error('File upload failed');
          const newFileItems: FileItem[] = uploadResults.map((result: UploadResult) => {
            const fileItem: FileItem = {
              file_id: result.file_id,
              file_path: result.file_path,
              original_file_name: result.original_filename,
              file_type: result.file_type,
            };
            if (result.file_type === 'url' || result.file_url) fileItem.url = result.file_type === 'url' ? result.file_url : result.file_path;
            return fileItem;
          });
          dataToSubmit.files = newFileItems;
          dataToSubmit.content = `Files: ${newFileItems.map((f) => f.original_file_name).join(', ')}`;
        } else if (editingItem && formData.files && formData.files.length > 0) {
          dataToSubmit.files = formData.files.map((fileItem) => (typeof fileItem === 'object' && fileItem !== null ? fileItem : fileItem));
        }
      }

      if (!dataToSubmit.urls && dataToSubmit.urls.length === 0) delete dataToSubmit.urls;

      if (editingItem) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        await updateKnowledgeItem(editingItem.id, dataToSubmit as any);
        setSuccess(`Knowledge base item "${dataToSubmit.name}" updated successfully`);

        if (syncAfterSaveRef.current) {
          syncAfterSaveRef.current = false;
          setEditingItem((prev) => (prev ? { ...prev, ...dataToSubmit } : null) as KnowledgeItem);
          await performSync();
          return;
        }
      } else {
        dataToSubmit.id = uuidv4();
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        await createKnowledgeItem(dataToSubmit as any);
        setSuccess(`Knowledge base item "${dataToSubmit.name}" created successfully`);
      }

      navigate('/knowledge-base');
    } catch (err) {
      let errorMessage = (err as Error).message || String(err);
      if (errorMessage.includes('400')) errorMessage = 'A knowledge base with this name already exists.';
      toast.error(`Failed to ${editingItem ? 'update' : 'create'} knowledge base: ${errorMessage}`);
    } finally {
      setLoading(false);
    }
  };

  if (loading && isEditMode && !editingItem) {
    return (
      <SidebarProvider>
        <div className="min-h-screen flex w-full overflow-x-hidden">
          {!isMobile && <AppSidebar />}
          <main className="flex-1 flex flex-col bg-zinc-100 min-w-0 relative">
            <SidebarTrigger className="fixed top-4 z-10 h-8 w-8 bg-white/50 backdrop-blur-sm hover:bg-white/70 rounded-full shadow-md transition-[left] duration-200" />
            <div className="flex-1 flex items-center justify-center">
              <div className="text-sm text-gray-500">Loading...</div>
            </div>
          </main>
        </div>
      </SidebarProvider>
    );
  }

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full overflow-x-hidden">
        {!isMobile && <AppSidebar />}
        <main className="flex-1 flex flex-col bg-zinc-100 min-w-0 relative peer-data-[state=expanded]:md:ml-[calc(var(--sidebar-width)-2px)] peer-data-[state=collapsed]:md:ml-0 transition-[margin] duration-200">
          <SidebarTrigger className="fixed top-4 z-10 h-8 w-8 bg-white/50 backdrop-blur-sm hover:bg-white/70 rounded-full shadow-md transition-[left] duration-200" />
          <div className="flex-1 p-4 sm:p-6 lg:p-8">
            <div className="max-w-7xl mx-auto space-y-8">
              <div className="flex items-center">
                <Button variant="ghost" size="icon" onClick={() => navigate('/knowledge-base')} className="mr-2">
                  <ChevronLeft className="h-5 w-5" />
                </Button>
                <h2 className="text-2xl font-bold tracking-tight">
                  {isEditMode ? 'Edit Knowledge Base' : 'New Knowledge Base'}
                </h2>
              </div>

              {error && (
                <div className="flex items-center gap-2 p-3 text-destructive bg-destructive/10 rounded-md">
                  <AlertCircle className="h-4 w-4" />
                  <p className="text-sm font-medium">{error}</p>
                </div>
              )}

              {success && (
                <div className="flex items-center gap-2 p-3 text-green-600 bg-green-50 rounded-md">
                  <CheckCircle2 className="h-4 w-4" />
                  <p className="text-sm font-medium">{success}</p>
                </div>
              )}

              <form ref={formRef} onSubmit={handleSubmit}>
                <div className="space-y-6">
                  <div className="rounded-lg border bg-white">
                    {/* Basic Information */}
                    <div className="p-6">
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div>
                          <h3 className="text-lg font-semibold">Basic Information</h3>
                          <p className="text-sm text-gray-500 mt-1">Basic information about the knowledge base.</p>
                        </div>

                        <div className="md:col-span-2 space-y-6">
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div>
                              <div className="mb-1">Name</div>
                              <Input
                                id="name"
                                name="name"
                                value={formData.name}
                                onChange={handleInputChange}
                                placeholder="Name for this knowledge base item"
                              />
                            </div>
                            <div>
                              <div className="mb-1">Description</div>
                              <Input
                                id="description"
                                name="description"
                                value={formData.description}
                                onChange={handleInputChange}
                                placeholder="Brief description of this knowledge base item"
                              />
                            </div>
                          </div>

                          <div>
                            <div className="mb-1">Type</div>
                            <Select
                              value={formData.type}
                              onValueChange={(value) =>
                                handleInputChange({
                                  target: { name: 'type', value },
                                } as React.ChangeEvent<HTMLInputElement>)
                              }
                            >
                              <SelectTrigger id="type">
                                <SelectValue placeholder="Select content type" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="text">Text</SelectItem>
                                <SelectItem value="file">Files</SelectItem>
                                <SelectItem value="url">URLs</SelectItem>
                                <SelectItem value="s3">S3</SelectItem>
                                <SelectItem value="sharepoint">Sharepoint</SelectItem>
                                <SelectItem key="smb_share_folder" value="smb_share_folder">
                                  Network Share/Folder
                                </SelectItem>
                                <SelectItem value="azure_blob">Azure Blob Storage</SelectItem>
                                <SelectItem value="google_bucket">Google Bucket Storage</SelectItem>
                                <SelectItem value="zendesk">Zendesk</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>

                          {formData.type === 'text' ? (
                            <div>
                              <div className="mb-1">Content</div>
                              <Textarea
                                id="content"
                                name="content"
                                value={formData.content}
                                onChange={handleInputChange}
                                placeholder="The knowledge content"
                                rows={4}
                                className="min-h-32"
                              />
                            </div>
                          ) : formData.type === 'url' ? (
                            <div className="space-y-4">
                              <div className="flex items-center justify-between">
                                <div className="mb-1">URLs</div>
                                <Button type="button" variant="outline" size="sm" onClick={addUrl}>
                                  <Plus className="w-4 h-4 mr-1" /> Add URL
                                </Button>
                              </div>
                              {urls.map((url, index) => (
                                <div key={index} className="flex gap-2 items-end">
                                  <div className="flex-1">
                                    <Input
                                      id={`url-${index}`}
                                      value={url}
                                      onChange={(e) => handleUrlChange(index, e.target.value)}
                                      placeholder="Enter URL (e.g., https://example.com)"
                                      type="url"
                                    />
                                  </div>
                                  {urls.length > 1 && (
                                    <Button type="button" variant="ghost" size="sm" onClick={() => removeUrl(index)}>
                                      <X className="w-4 h-4" />
                                    </Button>
                                  )}
                                </div>
                              ))}
                              <div className="mt-4 rounded-lg border bg-white p-4">
                                <div className="flex items-center justify-between">
                                  <div className="flex-1 pr-4">
                                    <div className="text-sm font-medium text-gray-900">Use HTTP request</div>
                                    <p className="text-sm text-gray-500 mt-1">
                                      Fetch content via a direct HTTP request instead of browser scraping.
                                    </p>
                                  </div>
                                  <Switch
                                    checked={formData.use_http_request || false}
                                    onCheckedChange={(checked) =>
                                      setFormData((prev) => ({ ...prev, use_http_request: checked }))
                                    }
                                  />
                                </div>
                              </div>
                              <div className="mt-4">
                                <div className="space-y-2">
                                  <div className="flex justify-between items-center">
                                    <Label>Custom Headers (optional)</Label>
                                    <Button
                                      type="button"
                                      size="sm"
                                      variant="outline"
                                      className="h-6 text-xs"
                                      onClick={() =>
                                        setUrlHeaders((prev) => [
                                          ...prev,
                                          { id: uuidv4(), key: '', value: '', keyType: 'known' },
                                        ])
                                      }
                                    >
                                      <Plus className="h-3 w-3 mr-1" /> Add Header
                                    </Button>
                                  </div>
                                  <div className="space-y-2">
                                    <datalist id="known-url-headers">
                                      {KNOWN_HTTP_HEADERS.map((key) => (
                                        <option key={key} value={key} />
                                      ))}
                                    </datalist>
                                    {urlHeaders.map((header, idx) => (
                                      <div key={`url-header-${idx}`} className="flex items-center gap-2 w-full">
                                        <Input
                                          placeholder="Header name"
                                          value={header.key}
                                          onChange={(e) =>
                                            setUrlHeaders((prev) =>
                                              prev.map((row) =>
                                                row.id === header.id
                                                  ? {
                                                      ...row,
                                                      key: e.target.value,
                                                      keyType: KNOWN_HTTP_HEADERS.includes(e.target.value)
                                                        ? 'known'
                                                        : 'custom',
                                                    }
                                                  : row
                                              )
                                            )
                                          }
                                          list="known-url-headers"
                                          className="flex-1 text-xs min-w-0 w-full"
                                        />
                                        <Input
                                          placeholder="Value"
                                          value={header.value}
                                          onChange={(e) =>
                                            setUrlHeaders((prev) =>
                                              prev.map((row) =>
                                                row.id === header.id ? { ...row, value: e.target.value } : row
                                              )
                                            )
                                          }
                                          className="flex-1 text-xs min-w-0 w-full"
                                        />
                                        <Button
                                          type="button"
                                          size="icon"
                                          variant="ghost"
                                          className="h-6 w-6 flex-shrink-0"
                                          onClick={() =>
                                            setUrlHeaders((prev) => prev.filter((row) => row.id !== header.id))
                                          }
                                        >
                                          <X className="h-3.5 w-3.5" />
                                        </Button>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              </div>
                            </div>
                          ) : formData.type === 'file' ? (
                            <div>
                              <div className="mb-1">Upload Files</div>
                              <div className="flex flex-col gap-2">
                                <div className="flex items-center justify-center w-full border-2 border-dashed border-border rounded-md cursor-pointer">
                                  <label
                                    htmlFor="file-upload"
                                    className="flex flex-col items-center gap-2 cursor-pointer w-full p-6"
                                  >
                                    <Upload className="h-10 w-10 text-muted-foreground" />
                                    <span className="text-sm font-medium text-muted-foreground">
                                      {selectedFiles.length > 0
                                        ? `${selectedFiles.length} file(s) selected`
                                        : formData.files && formData.files.length > 0
                                          ? 'Replace files'
                                          : 'Select files to upload'}
                                    </span>
                                    <input
                                      id="file-upload"
                                      type="file"
                                      multiple
                                      onChange={handleFileChange}
                                      disabled={isUploading}
                                      accept={acceptedFileTypes.join(',')}
                                      className="hidden"
                                    />
                                  </label>
                                </div>
                                {selectedFiles.length > 0 && (
                                  <div className="space-y-2">
                                    {selectedFiles.map((file, index) => (
                                      <div
                                        key={index}
                                        className="flex items-center justify-between p-2 bg-muted rounded-md"
                                      >
                                        <div className="flex items-center gap-2">
                                          <FilePlus className="h-4 w-4" />
                                          <span className="text-sm">
                                            {file.name} ({(file.size / 1024).toFixed(1)} KB)
                                          </span>
                                        </div>
                                        <Button
                                          type="button"
                                          variant="ghost"
                                          size="icon"
                                          onClick={() => setSelectedFiles((prev) => prev.filter((_, i) => i !== index))}
                                          className="h-8 w-8"
                                        >
                                          <X className="h-4 w-4" />
                                        </Button>
                                      </div>
                                    ))}
                                  </div>
                                )}
                                {formData.files && formData.files.length > 0 && selectedFiles.length === 0 && (
                                  <div className="space-y-2">
                                    {formData.files.map((fileItem, index) => {
                                      const fileLinkUrl = getFileUrl(fileItem);
                                      const canLink =
                                        fileLinkUrl &&
                                        (fileLinkUrl.startsWith('http://') ||
                                          fileLinkUrl.startsWith('https://') ||
                                          fileLinkUrl.startsWith('/'));
                                      return (
                                        <div
                                          key={index}
                                          className="flex items-center justify-between p-2 bg-muted rounded-md"
                                        >
                                          <div className="flex items-center gap-2">
                                            <Database className="h-4 w-4" />
                                            <span className="text-sm">
                                              {maskFileName(getFileDisplayName(fileItem))}
                                            </span>
                                          </div>
                                          <div className="flex items-center gap-1">
                                            {canLink ? (
                                              <a
                                                href={fileLinkUrl}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="inline-flex items-center justify-center h-8 w-8 p-0 rounded-md hover:bg-accent hover:text-accent-foreground"
                                                title="Open file"
                                              >
                                                <Download className="h-4 w-4" />
                                              </a>
                                            ) : (
                                              <span className="inline-flex h-8 w-8 items-center justify-center text-muted-foreground">
                                                <Download className="h-4 w-4" />
                                              </span>
                                            )}
                                            {editingItem && (
                                              <Button
                                                type="button"
                                                variant="ghost"
                                                size="icon"
                                                className="h-8 w-8"
                                                title="Remove file"
                                                onClick={() =>
                                                  setFormData((prev) => ({
                                                    ...prev,
                                                    files: prev.files?.filter((_, i) => i !== index) ?? [],
                                                  }))
                                                }
                                              >
                                                <Trash2 className="h-4 w-4" />
                                              </Button>
                                            )}
                                          </div>
                                        </div>
                                      );
                                    })}
                                  </div>
                                )}
                                {isUploading && (
                                  <div className="p-2 space-y-2">
                                    <div className="text-sm text-muted-foreground">
                                      Uploading files... {uploadProgress > 0 ? `${uploadProgress}%` : 'Please wait.'}
                                    </div>
                                    <Progress value={uploadProgress} className="h-2" />
                                  </div>
                                )}
                              </div>
                            </div>
                          ) : (
                            <div>
                              <div className="mb-1">Data Source</div>
                              <Select
                                value={formData.sync_source_id || ''}
                                onValueChange={(value) => {
                                  if (value === '__create__') {
                                    setIsDataSourceDialogOpen(true);
                                    return;
                                  }
                                  setFormData((prev) => ({ ...prev, sync_source_id: value }));
                                }}
                              >
                                <SelectTrigger className="w-full">
                                  <SelectValue placeholder="Select a data source" />
                                </SelectTrigger>
                                <SelectContent>
                                  {availableSources.map((source) => (
                                    <SelectItem key={source.id} value={source.id}>
                                      {source.name}
                                    </SelectItem>
                                  ))}
                                  <CreateNewSelectItem />
                                </SelectContent>
                              </Select>

                              {formData.type === 'sharepoint' && (
                                <div className="mt-4">
                                  <div className="mb-1">SharePoint Site Link</div>
                                  <Input
                                    id="sharepoint-url"
                                    type="url"
                                    value={urls[0] || ''}
                                    onChange={(e) => handleUrlChange(0, e.target.value)}
                                    placeholder="https://yourcompany.sharepoint.com/sites/..."
                                  />
                                </div>
                              )}

                              {formData.type === 'zendesk' && (
                                <div className="flex flex-col gap-6 mt-6">
                                  <div className="rounded-lg border bg-white p-4">
                                    <div className="flex items-center justify-between">
                                      <div className="flex-1 pr-4">
                                        <div className="text-sm font-medium text-gray-900">
                                          Allow Unpublished Articles
                                        </div>
                                        <p className="text-sm text-gray-500 mt-1">
                                          Allow unpublished articles to be indexed in the knowledge base.
                                        </p>
                                      </div>
                                      <Switch
                                        checked={
                                          (formData.extra_metadata?.allow_unpublished_articles as boolean) || false
                                        }
                                        onCheckedChange={(checked) =>
                                          setFormData(
                                            (prev) =>
                                              ({
                                                ...prev,
                                                extra_metadata: {
                                                  ...prev.extra_metadata,
                                                  allow_unpublished_articles: checked,
                                                },
                                              }) as KnowledgeItem
                                          )
                                        }
                                      />
                                    </div>
                                  </div>
                                  <div className="rounded-lg border bg-white p-4">
                                    <div className="flex items-center justify-between">
                                      <div className="flex-1 pr-4">
                                        <div className="text-sm font-medium text-gray-900">Allow HTML Content</div>
                                        <p className="text-sm text-gray-500 mt-1">
                                          Allow HTML content to be indexed in the knowledge base.
                                        </p>
                                      </div>
                                      <Switch
                                        checked={(formData.extra_metadata?.allow_html_content as boolean) || false}
                                        onCheckedChange={(checked) =>
                                          setFormData(
                                            (prev) =>
                                              ({
                                                ...prev,
                                                extra_metadata: {
                                                  ...prev.extra_metadata,
                                                  allow_html_content: checked,
                                                },
                                              }) as KnowledgeItem
                                          )
                                        }
                                      />
                                    </div>
                                  </div>
                                </div>
                              )}

                              {['s3', 'sharepoint', 'smb_share_folder', 'azure_blob', 'zendesk'].includes(
                                formData.type
                              ) && (
                                <div className="col-span-2 space-y-4">
                                  <div className="flex flex-col gap-6 mt-6">
                                    <div className="rounded-lg border bg-white p-4">
                                      <div className="flex items-center justify-between">
                                        <div className="flex-1 pr-4">
                                          <div className="text-sm font-medium text-gray-900">Sync Schedule</div>
                                          <p className="text-sm text-gray-500 mt-1">
                                            Enable automatic syncing on a schedule.
                                          </p>
                                        </div>
                                        <Switch
                                          id="sync_active"
                                          checked={formData.sync_active || false}
                                          onCheckedChange={(checked) =>
                                            setFormData((prev) => ({ ...prev, sync_active: checked }))
                                          }
                                        />
                                      </div>
                                      {formData.sync_active && (
                                        <div className="mt-3">
                                          <Input
                                            id="sync_schedule"
                                            name="sync_schedule"
                                            value={formData.sync_schedule ?? ''}
                                            onChange={(e) =>
                                              setFormData((prev) => ({ ...prev, sync_schedule: e.target.value }))
                                            }
                                            placeholder="e.g. every 15':  */15 * * * *"
                                            className="w-full"
                                          />
                                        </div>
                                      )}
                                    </div>

                                    {editingItem && (
                                      <div className="flex flex-row flex-wrap items-center justify-between gap-3">
                                        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
                                          {(editingItem.last_synced ||
                                            editingItem.last_sync_status ||
                                            editingItem.last_sync_error) && (
                                            <>
                                              <span className="text-xs text-gray-600">
                                                Last sync
                                                {editingItem.last_synced
                                                  ? `: ${new Date(editingItem.last_synced).toLocaleString()}`
                                                  : ''}
                                              </span>
                                              {editingItem.last_sync_status ? (
                                                isSyncErrorStatus(editingItem.last_sync_status) &&
                                                editingItem.last_sync_error ? (
                                                  <Popover>
                                                    <PopoverTrigger asChild>
                                                      <button
                                                        type="button"
                                                        className="inline-flex rounded-full border-0 bg-transparent p-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                                                      >
                                                        <Badge
                                                          variant={syncStatusBadgeVariant(editingItem.last_sync_status)}
                                                          className="cursor-pointer"
                                                        >
                                                          {editingItem.last_sync_status}
                                                        </Badge>
                                                      </button>
                                                    </PopoverTrigger>
                                                    <PopoverContent
                                                      align="start"
                                                      className="w-80 max-w-[min(90vw,24rem)]"
                                                    >
                                                      <p className="mb-2 text-xs font-medium text-muted-foreground">
                                                        Error details
                                                      </p>
                                                      <p className="whitespace-pre-wrap break-words text-sm text-destructive">
                                                        {editingItem.last_sync_error}
                                                      </p>
                                                    </PopoverContent>
                                                  </Popover>
                                                ) : (
                                                  <Badge variant={syncStatusBadgeVariant(editingItem.last_sync_status)}>
                                                    {editingItem.last_sync_status}
                                                  </Badge>
                                                )
                                              ) : null}
                                              {editingItem.last_sync_error &&
                                              !isSyncErrorStatus(editingItem.last_sync_status) ? (
                                                <Badge
                                                  variant="secondary"
                                                  className="max-w-[min(100%,20rem)] shrink truncate font-normal sm:max-w-[28rem]"
                                                  title={editingItem.last_sync_error}
                                                >
                                                  {editingItem.last_sync_error}
                                                </Badge>
                                              ) : null}
                                            </>
                                          )}
                                        </div>
                                        <Button
                                          type="button"
                                          variant="outline"
                                          onClick={handleSyncNow}
                                          disabled={isSyncing}
                                          className="min-w-[130px] shrink-0 rounded-full"
                                        >
                                          <div className="flex items-center gap-2">
                                            <RefreshCw className={`h-4 w-4 ${isSyncing ? 'animate-spin' : ''}`} />
                                            {isSyncing ? 'Syncing...' : 'Sync Now'}
                                          </div>
                                        </Button>
                                      </div>
                                    )}

                                    <Collapsible>
                                      <CollapsibleTrigger className="group flex items-center justify-between w-full p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
                                        <h4 className="text-sm font-medium">Processing & Output</h4>
                                        <ChevronDown className="h-4 w-4 group-data-[state=open]:hidden" />
                                        <ChevronUp className="h-4 w-4 hidden group-data-[state=open]:block" />
                                      </CollapsibleTrigger>
                                      <CollapsibleContent className="mt-3">
                                        <div className="space-y-4 pl-4">
                                          <div>
                                            <label className="block text-sm font-medium">Processing Filter</label>
                                            <Input
                                              name="processing_filter"
                                              value={formData.processing_filter || ''}
                                              onChange={handleInputChange}
                                              placeholder="e.g. *.pdf or contains:report"
                                              className="mt-1"
                                            />
                                          </div>
                                          <div>
                                            <label className="block text-sm font-medium">Processing Mode</label>
                                            <Select
                                              value={formData.processing_mode || 'none'}
                                              onValueChange={(value) =>
                                                setFormData((prev) => ({
                                                  ...prev,
                                                  processing_mode: value === 'none' ? null : value,
                                                }))
                                              }
                                            >
                                              <SelectTrigger className="mt-1 w-full">
                                                <SelectValue placeholder="None" />
                                              </SelectTrigger>
                                              <SelectContent>
                                                <SelectItem value="none">None</SelectItem>
                                                <SelectItem value="extract">Extract Only</SelectItem>
                                                <SelectItem value="transcribe">Transcribe</SelectItem>
                                              </SelectContent>
                                            </Select>
                                          </div>

                                          {formData.processing_mode === 'transcribe' && (
                                            <div>
                                              <label className="block text-sm font-medium">Transcription Engine</label>
                                              <Select
                                                value={formData.transcription_engine}
                                                onValueChange={(value) =>
                                                  setFormData((prev) => ({ ...prev, transcription_engine: value }))
                                                }
                                              >
                                                <SelectTrigger className="mt-1 w-full">
                                                  <SelectValue placeholder="Select engine" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                  <SelectItem value="openai_whisper">OpenAI Whisper</SelectItem>
                                                  <SelectItem value="google_chirp3">Google Chirp 3</SelectItem>
                                                </SelectContent>
                                              </Select>
                                            </div>
                                          )}

                                          <div>
                                            <label className="block text-sm font-medium">LLM Analyst (optional)</label>
                                            <Select
                                              value={formData.llm_analyst_id || 'none'}
                                              onValueChange={(value) =>
                                                setFormData((prev) => ({
                                                  ...prev,
                                                  llm_analyst_id: value === 'none' ? null : value,
                                                }))
                                              }
                                            >
                                              <SelectTrigger className="mt-1 w-full">
                                                <SelectValue placeholder="Select an analyst" />
                                              </SelectTrigger>
                                              <SelectContent>
                                                <SelectItem value="none">None</SelectItem>
                                                {llmAnalysts.map((a) => (
                                                  <SelectItem key={a.id} value={String(a.id)}>
                                                    {a.name}
                                                  </SelectItem>
                                                ))}
                                              </SelectContent>
                                            </Select>
                                          </div>

                                          {formData.processing_mode === 'transcribe' && (
                                            <div className="flex items-center justify-between">
                                              <label className="text-sm font-medium">Save In Conversation</label>
                                              <Switch
                                                checked={formData.save_in_conversation}
                                                onCheckedChange={(checked) =>
                                                  setFormData((prev) => ({ ...prev, save_in_conversation: checked }))
                                                }
                                              />
                                            </div>
                                          )}

                                          <div className="flex flex-col gap-2">
                                            <div className="flex items-center gap-2 justify-between">
                                              <label className="text-sm font-medium">
                                                Save Output in source location
                                              </label>
                                              <Switch
                                                checked={formData.save_output}
                                                onCheckedChange={(checked) =>
                                                  setFormData((prev) => ({ ...prev, save_output: checked }))
                                                }
                                              />
                                            </div>
                                            {formData.save_output && (
                                              <Input
                                                placeholder="Output path (e.g. /storage/out/)"
                                                value={formData.save_output_path}
                                                onChange={(e) =>
                                                  setFormData((prev) => ({ ...prev, save_output_path: e.target.value }))
                                                }
                                                className="flex-1"
                                              />
                                            )}
                                          </div>
                                        </div>
                                      </CollapsibleContent>
                                    </Collapsible>
                                  </div>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="my-0 border-t border-gray-200" />

                    <DynamicRagConfigSection
                      ragConfig={dynamicRagConfig}
                      onChange={handleRagConfigChange}
                      showOnlyRequired={true}
                      knowledgeId={editingItem?.id}
                      initialLegraFinalize={Boolean(
                        (editingItem as KnowledgeItem & { legra_finalize?: boolean })?.legra_finalize
                      )}
                    />
                  </div>

                  <div className="flex justify-end gap-3">
                    <Button type="button" variant="outline" onClick={() => navigate('/knowledge-base')}>
                      Cancel
                    </Button>
                    <Button type="submit" disabled={loading || isUploading}>
                      {loading || isUploading
                        ? 'Saving...'
                        : isEditMode
                          ? 'Update Knowledge Base'
                          : 'Create Knowledge Base'}
                    </Button>
                  </div>
                </div>
              </form>
            </div>
          </div>
        </main>
      </div>

      {isDataSourceDialogOpen && (
        <DataSourceDialog
          isOpen={isDataSourceDialogOpen}
          onOpenChange={setIsDataSourceDialogOpen}
          onDataSourceSaved={() => {
            setIsDataSourceDialogOpen(false);
            fetchSources();
          }}
        />
      )}

      <ConfirmDialog
        isOpen={isSyncSaveDialogOpen}
        onOpenChange={setIsSyncSaveDialogOpen}
        onConfirm={handleSaveAndSync}
        isInProgress={false}
        title="Save and Sync?"
        description="You have unsaved changes. Save first and then trigger sync?"
        primaryButtonText="Save & Sync"
      />
    </SidebarProvider>
  );
};

export default KnowledgeBaseForm;
