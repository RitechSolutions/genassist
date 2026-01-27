import React, { useState, useEffect } from "react";
import { toast } from "react-hot-toast";
import {
  getAllKnowledgeItems,
  createKnowledgeItem,
  updateKnowledgeItem,
  deleteKnowledgeItem,
  uploadFiles as apiUploadFiles,
} from "@/services/api";
import { getAllDataSources } from "@/services/dataSources";

import { getAllLLMAnalysts } from "@/services/llmAnalyst";

import { v4 as uuidv4 } from "uuid";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Textarea } from "@/components/textarea";
import { Switch } from "@/components/switch";
import { Label } from "@/components/label";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { CreateNewSelectItem } from "@/components/CreateNewSelectItem";
import {
  FilePlus,
  Upload,
  Database,
  X,
  Pencil,
  AlertCircle,
  CheckCircle2,
  Plus,
  Search,
  FileText,
  ChevronLeft,
  Trash2,
} from "lucide-react";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { RagConfigValues } from "../types/ragSchema";
import {
  LegacyRagConfig,
  DEFAULT_LEGACY_RAG_CONFIG,
} from "../utils/ragDefaults";
import DynamicRagConfigSection from "./DynamicRagConfigSection";
import { DataSourceDialog } from "@/views/DataSources/components/DataSourceDialog";

interface KnowledgeItem {
  id: string;
  name: string;
  description: string;
  content: string;
  type: string;
  sync_source_id: string;
  llm_provider_id?: string | null;
  sync_schedule?: string;
  sync_active?: boolean;
  files?: string[];
  rag_config?: LegacyRagConfig;
  url?: string;
  use_http_request?: boolean;
  extra_metadata?: Record<string, any>;
  processing_filter?: string | null;
  llm_analyst_id?: string | null;
  processing_mode?: string | null;

  transcription_engine?: string | null;
  save_in_conversation?: boolean;
  save_output?: boolean;
  save_output_path?: string;

  [key: string]: unknown;
}

type UrlHeaderRow = {
  id: string;
  key: string;
  value: string;
  keyType: "known" | "custom";
};

const DEFAULT_FORM_DATA: KnowledgeItem = {
  id: uuidv4(),
  name: "",
  description: "",
  content: "",
  type: "text",
  sync_source_id: null,
  llm_provider_id: null,
  files: [],
  url: null,
  use_http_request: false,
  rag_config: DEFAULT_LEGACY_RAG_CONFIG,
  processing_filter: "",
  llm_analyst_id: null,
  processing_mode: null,

  transcription_engine: "openai_whisper",
  save_in_conversation: false,
  save_output: false,
  save_output_path: "",
};

const KNOWN_HTTP_HEADERS = [
  "Authorization",
  "User-Agent",
  "Accept",
  "Accept-Language",
  "Content-Type",
  "Cache-Control",
  "If-None-Match",
  "If-Modified-Since",
];

const KnowledgeBaseManager: React.FC = () => {
  const [items, setItems] = useState<KnowledgeItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [showForm, setShowForm] = useState<boolean>(false);

  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [availableSources, setAvailableSources] = useState([]);
  // const [cronError, setCronError] = useState<string | null>(null);

  const [knowledgeBaseToDelete, setKnowledgeBaseToDelete] =
    useState<Partial<KnowledgeItem> | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const [llmProviders, setLlmProviders] = useState([]);
  const [llmAnalysts, setLlmAnalysts] = useState([]);

  const [editingItem, setEditingItem] = useState<KnowledgeItem | null>(null);
  const [formData, setFormData] = useState<KnowledgeItem>(DEFAULT_FORM_DATA);
  const [dynamicRagConfig, setDynamicRagConfig] = useState<RagConfigValues>({});
  const [isDataSourceDialogOpen, setIsDataSourceDialogOpen] = useState(false);
  const [urlHeaders, setUrlHeaders] = useState<UrlHeaderRow[]>([]);

  useEffect(() => {
    fetchItems();
  }, []);

  const fetchItems = async () => {
    try {
      setLoading(true);
      const data = await getAllKnowledgeItems();
      setItems(data as KnowledgeItem[]);
      setError(null);
    } catch (err) {
      setError("Failed to load knowledge base items");
    } finally {
      setLoading(false);
    }
  };

  // useEffect(() => {
  //   const fetchLLMProviders = async () => {
  //     try {
  //       const result = await getAllLLMProviders();
  //       setLlmProviders(result.filter((p) => p.is_active === 1));
  //     } catch (err) {
  //       console.error("Failed to load LLM providers", err);
  //     }
  //   };

  //   fetchLLMProviders();
  // }, []);
  useEffect(() => {
    const fetchLLMAnalysts = async () => {
      try {
        const analysts = await getAllLLMAnalysts();
        setLlmAnalysts(analysts.filter((a) => a.is_active === 1));
      } catch (err) {
        // ignore
      }
    };

    fetchLLMAnalysts();
  }, []);

  const targetTypes = {
    s3: "S3",
    sharepoint: "o365",
    smb_share_folder: "smb_share_folder",
    azure_blob: "azure_blob",
    google_bucket: "gmail",
    zendesk: "zendesk",
  };

  useEffect(() => {
    const fetchSources = async () => {
      if (formData.type in targetTypes) {
        const allSources = await getAllDataSources();
        console.log(allSources);
        const targetType = targetTypes[formData.type];

        const filtered = allSources.filter(
          (source) => source.source_type.toLowerCase() === targetType.toLowerCase(),
        );
        setAvailableSources(filtered);
      }
    };

    fetchSources();
  }, [formData.type]);

  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleRagConfigChange = (updatedRagConfig: RagConfigValues) => {
    setDynamicRagConfig(updatedRagConfig);
    const enabledRagTypes = Object.keys(updatedRagConfig).map((ragType) => {
      return updatedRagConfig[ragType].enabled;
    });
    const ragConfig = updatedRagConfig as LegacyRagConfig;
    ragConfig.enabled = enabledRagTypes.some((enabled) => enabled);

    // Since RagConfigValues now matches the legacy format, use directly
    setFormData((prev) => ({
      ...prev,
      rag_config: ragConfig,
    }));
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files ? Array.from(e.target.files) : [];
    setSelectedFiles(files);

    setFormData((prev) => ({
      ...prev,
      content:
        files.length > 0 ? `Files: ${files.map((f) => f.name).join(", ")}` : "",
    }));
  };

  const uploadFiles = async () => {
    if (selectedFiles.length === 0) return null;

    setIsUploading(true);

    try {
      const result = await apiUploadFiles(selectedFiles);
      return result;
    } catch (error) {
      setError(
        `Failed to upload files: ${
          error instanceof Error ? error.message : String(error)
        }`,
      );
      return null;
    } finally {
      setIsUploading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const requiredFields = [
      { label: "name", isEmpty: !formData.name },
      { label: "description", isEmpty: !formData.description },
    ];

    if (formData.type === "text") {
      requiredFields.push({ label: "content", isEmpty: !formData.content });
    }

    if (formData.type === "file") {
      requiredFields.push({
        label: "file",
        isEmpty:
          selectedFiles.length === 0 &&
          (!formData.files || formData.files.length === 0),
      });
    }

    if (formData.type === "s3") {
      requiredFields.push({
        label: "source",
        isEmpty: !formData.sync_source_id,
      });
    }

    if (formData.type === "zendesk") {
      requiredFields.push({
        label: "source",
        isEmpty: !formData.sync_source_id,
      });

      if (formData.sync_active) {
        requiredFields.push({
          label: "sync schedule",
          isEmpty: !formData.sync_schedule,
        });
      }
    }

    if (["s3", "azure_blob"].includes(formData.type) && formData.sync_active) {
      requiredFields.push({
        label: "sync schedule",
        isEmpty: !formData.sync_schedule,
      });
    }

    if (formData.type === "url") {
      requiredFields.push({ label: "url", isEmpty: !formData.url });
      if (urlHeaders.length > 0) {
        urlHeaders.forEach((header) => {
          const hasKey = header.key.trim().length > 0;
          const hasValue = header.value.trim().length > 0;
          if (!hasKey || !hasValue) {
            requiredFields.push({
              label: "custom header",
              isEmpty: true,
            });
          }
        });
      }
    }
    if (formData.type === "sharepoint") {
      requiredFields.push(
        { label: "source", isEmpty: !formData.sync_source_id },
        { label: "url", isEmpty: !formData.url },
      );

      if (formData.sync_active) {
        requiredFields.push({
          label: "sync schedule",
          isEmpty: !formData.sync_schedule,
        });
      }
    }

    if (formData.type === "smb_share_folder") {
      requiredFields.push({
        label: "source",
        isEmpty: !formData.sync_source_id,
      });

      if (formData.sync_active) {
        requiredFields.push({
          label: "sync schedule",
          isEmpty: !formData.sync_schedule,
        });
      }
    }

    const missingFields = requiredFields
      .filter((field) => field.isEmpty)
      .map((field) => field.label)
      .map((label) => {
        if (label === "url") {
          return "URL";
        } else {
          return label.charAt(0).toUpperCase() + label.slice(1);
        }
      });

    if (missingFields.length > 0) {
      if (missingFields.length === 1) {
        toast.error(`${missingFields[0]} is required.`);
      } else {
        toast.error(`Please provide: ${missingFields.join(", ")}.`);
      }
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setSuccess(null);

      if (
        ["s3", "sharepoint", "smb_share_folder", "azure_blob", "zendesk"].includes(
          formData.type
        ) &&
        formData.sync_active &&
        !isValidCron(formData.sync_schedule)
      ) {
        throw new Error("Invalid cron expression. Expected format: * * * * *");
      }

      const dataToSubmit = { ...formData };

      const normalizedUrlHeaders = urlHeaders.reduce<Record<string, string>>(
        (acc, header) => {
          const key = header.key.trim();
          if (!key) return acc;
          acc[key] = header.value;
          return acc;
        },
        {}
      );
      const hasUrlHeaders = Object.keys(normalizedUrlHeaders).length > 0;

      // Move custom frontend-only fields into extra_metadata
      dataToSubmit.extra_metadata = {
        ...(dataToSubmit.extra_metadata || {}),
        use_http_request: dataToSubmit.use_http_request || false,
        http_headers:
          dataToSubmit.type === "url" && hasUrlHeaders
            ? normalizedUrlHeaders
            : null,
        processing_filter: dataToSubmit.processing_filter || null,
        llm_analyst_id: dataToSubmit.llm_analyst_id || null,
        processing_mode: dataToSubmit.processing_mode || null,

        transcription_engine:
          dataToSubmit.processing_mode === "transcribe"
            ? dataToSubmit.transcription_engine
            : null,

        save_in_conversation:
          dataToSubmit.processing_mode === "transcribe"
            ? dataToSubmit.save_in_conversation
            : false,

        save_output: dataToSubmit.save_output || false,
        save_output_path:
          dataToSubmit.save_output && dataToSubmit.save_output_path
            ? dataToSubmit.save_output_path
            : null,
      };

      // Remove them from the top-level payload
      delete dataToSubmit.processing_filter;
      delete dataToSubmit.llm_analyst_id;
      delete dataToSubmit.processing_mode;

      delete dataToSubmit.transcription_engine;
      delete dataToSubmit.save_in_conversation;
      delete dataToSubmit.save_output;
      delete dataToSubmit.save_output_path;
      delete dataToSubmit.use_http_request;
      //////////////////////////

      if (formData.type === "file" && selectedFiles.length > 0) {
        const uploadResults = await uploadFiles();

        if (!uploadResults || uploadResults.length === 0) {
          throw new Error("File upload failed");
        }

        dataToSubmit.files = uploadResults.map(
          (result: any) => result.file_path,
        );
        dataToSubmit.content = `Files: ${uploadResults
          .map((r: any) => r.original_filename)
          .join(", ")}`;
      }

      if (editingItem) {
        await updateKnowledgeItem(editingItem.id, dataToSubmit);
        setSuccess(
          `Knowledge base item "${dataToSubmit.name}" updated successfully`,
        );
      } else {
        //if (!dataToSubmit.id) {
        dataToSubmit.id = uuidv4();
        //}

        await createKnowledgeItem(dataToSubmit);
        setSuccess(
          `Knowledge base item "${dataToSubmit.name}" created successfully`,
        );
      }

      setFormData(DEFAULT_FORM_DATA);
      setDynamicRagConfig({});
      setSelectedFiles([]);
      setUrlHeaders([]);
      setEditingItem(null);
      setShowForm(false);
      fetchItems();
    } catch (err) {
      let errorMessage = err.message || String(err);

      if (errorMessage.includes("400")) {
        errorMessage = "A knowledge base with this name already exists.";
      }

      toast.error(
        `Failed to ${
          editingItem ? "update" : "create"
        } knowledge base: ${errorMessage}`,
      );
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    setFormData(DEFAULT_FORM_DATA);
    setDynamicRagConfig({});
    setSelectedFiles([]);
    setUrlHeaders([]);
    setEditingItem(null);
    setError(null);
    setSuccess(null);
    setShowForm(false);
  };

  const handleEdit = (item: KnowledgeItem) => {
    setEditingItem(item);

    setFormData({
      id: item.id,
      name: item.name,
      description: item.description,
      content: item.content,
      type: item.type || DEFAULT_FORM_DATA.type,
      sync_source_id: item.sync_source_id,
      url: item.url,
      use_http_request: item.extra_metadata?.use_http_request ?? false,
      llm_provider_id:
        item.llm_provider_id || DEFAULT_FORM_DATA.llm_provider_id,
      sync_schedule: item.sync_schedule || DEFAULT_FORM_DATA.sync_schedule,
      sync_active: item.sync_active || DEFAULT_FORM_DATA.sync_active,
      files: item.files || DEFAULT_FORM_DATA.files,
      rag_config: item.rag_config || DEFAULT_LEGACY_RAG_CONFIG,

      processing_filter: item.extra_metadata?.processing_filter ?? "",
      llm_analyst_id: item.extra_metadata?.llm_analyst_id ?? null,
      processing_mode: item.extra_metadata?.processing_mode ?? null,

      transcription_engine:
        item.extra_metadata?.transcription_engine ?? "openai_whisper",
      save_in_conversation: item.extra_metadata?.save_in_conversation ?? false,
      save_output: item.extra_metadata?.save_output ?? false,
      save_output_path: item.extra_metadata?.save_output_path ?? "",
    });

    const existingUrlHeaders =
      item.extra_metadata?.http_headers || item.extra_metadata?.custom_headers;
    if (existingUrlHeaders && typeof existingUrlHeaders === "object") {
      const rows = Object.entries(existingUrlHeaders as Record<string, string>)
        .map(([key, value]) => ({
          id: uuidv4(),
          key,
          value: value ?? "",
          keyType: KNOWN_HTTP_HEADERS.includes(key) ? "known" : "custom",
        }))
        .filter((row) => row.key);
      setUrlHeaders(rows);
    } else {
      setUrlHeaders([]);
    }

    setDynamicRagConfig(
      (item.rag_config || DEFAULT_LEGACY_RAG_CONFIG) as RagConfigValues,
    );

    setSelectedFiles([]);
    setShowForm(true);
  };

  const handleDeleteClick = async (id: string, name: string) => {
    setKnowledgeBaseToDelete({ id, name });
    setIsDeleteDialogOpen(true);
  };

  const handleDelete = async () => {
    if (!knowledgeBaseToDelete?.id || !deleteKnowledgeItem) return;

    try {
      setIsDeleting(true);
      await deleteKnowledgeItem(knowledgeBaseToDelete.id);
      toast.success(`Knowledge base deleted successfully.`);
      // setSuccess(`Knowledge base item "${name}" deleted successfully`);
      setItems((prev) => prev.filter((s) => s.id !== knowledgeBaseToDelete.id));
    } catch (err) {
      toast.error("Failed to delete knowledge base.");
      // setError(
      //   `Failed to delete knowledge base item: ${
      //     err instanceof Error ? err.message : String(err)
      //   }`
      // );
    } finally {
      setKnowledgeBaseToDelete(null);
      setIsDeleteDialogOpen(false);
      setIsDeleting(false);
    }
  };

  const filteredItems = items.filter((item) => {
    const matchesQuery =
      item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.description.toLowerCase().includes(searchQuery.toLowerCase());

    return (
      matchesQuery &&
      (item.type.toLowerCase() === typeFilter || typeFilter === "all")
    );
  });

  const isValidCron = (cron: string): boolean => {
    const cronRegex =
      /^(((\*|\d+)(-\d+)?)(\/\d+)?)(,((\*|\d+)(-\d+)?)(\/\d+)?)*\s+(((\*|\d+)(-\d+)?)(\/\d+)?)(,((\*|\d+)(-\d+)?)(\/\d+)?)*\s+(((\*|\d+)(-\d+)?)(\/\d+)?)(,((\*|\d+)(-\d+)?)(\/\d+)?)*\s+(((\*|\d+)(-\d+)?)(\/\d+)?)(,((\*|\d+)(-\d+)?)(\/\d+)?)*\s+(((\*|\d+)(-\d+)?)(\/\d+)?)(,((\*|\d+)(-\d+)?)(\/\d+)?)*$/;
    return cronRegex.test(cron.trim());
  };

  return (
    <div className="space-y-8">
      {showForm ? (
        <>
          <div className="flex items-center">
            <Button
              variant="ghost"
              size="icon"
              onClick={handleCancel}
              className="mr-2"
            >
              <ChevronLeft className="h-5 w-5" />
            </Button>
            <h2 className="text-2xl font-bold tracking-tight">
              {editingItem ? "Edit Knowledge Base" : "New Knowledge Base"}
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

          <form onSubmit={handleSubmit}>
            <div className="space-y-6">
              <div className="rounded-lg border bg-white">
                {/* Basic Information */}
                <div className="p-6">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div>
                      <h3 className="text-lg font-semibold">
                        Basic Information
                      </h3>
                      <p className="text-sm text-gray-500 mt-1">
                        Basic information about the knowledge base.
                      </p>
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
                              target: { name: "type", value },
                            } as React.ChangeEvent<HTMLInputElement>)
                          }
                        >
                          <SelectTrigger id="type">
                            <SelectValue placeholder="Select content type" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="text">Text</SelectItem>
                            <SelectItem value="file">File</SelectItem>
                            <SelectItem value="url">Url</SelectItem>
                            <SelectItem value="s3">S3</SelectItem>
                            <SelectItem value="sharepoint">
                              Sharepoint
                            </SelectItem>
                            <SelectItem
                              key="smb_share_folder"
                              value="smb_share_folder"
                            >
                              Network Share/Folder
                            </SelectItem>
                            <SelectItem value="azure_blob">
                              Azure Blob Storage
                            </SelectItem>
                            <SelectItem value="google_bucket">
                              Google Bucket Storage
                            </SelectItem>
                            <SelectItem value="zendesk">Zendesk</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      {formData.type === "text" ? (
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
                      ) : formData.type === "url" ? (
                        <div>
                          <div className="mb-1">URL</div>
                          <Input
                            id="url"
                            name="url"
                            value={formData.url}
                            onChange={handleInputChange}
                            placeholder="Enter URL (e.g., https://example.com)"
                            type="url"
                          />
                          <div className="mt-4 rounded-lg border bg-white p-4">
                            <div className="flex items-center justify-between">
                              <div className="flex-1 pr-4">
                                <div className="text-sm font-medium text-gray-900">
                                  Use HTTP request
                                </div>
                                <p className="text-sm text-gray-500 mt-1">
                                  Fetch content via a direct HTTP request
                                  instead of browser scraping.
                                </p>
                              </div>
                              <Switch
                                checked={formData.use_http_request || false}
                                onCheckedChange={(checked) =>
                                  setFormData((prev) => ({
                                    ...prev,
                                    use_http_request: checked,
                                  }))
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
                                      {
                                        id: uuidv4(),
                                        key: "",
                                        value: "",
                                        keyType: "known",
                                      },
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
                                  <div
                                    key={`url-header-${idx}`}
                                    className="flex items-center gap-2 w-full"
                                  >
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
                                                  keyType: KNOWN_HTTP_HEADERS.includes(
                                                    e.target.value
                                                  )
                                                    ? "known"
                                                    : "custom",
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
                                            row.id === header.id
                                              ? {
                                                  ...row,
                                                  value: e.target.value,
                                                }
                                              : row
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
                                        setUrlHeaders((prev) =>
                                          prev.filter(
                                            (row) => row.id !== header.id
                                          )
                                        )
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
                      ) : formData.type === "file" ? (
                        <div>
                          <div className="mb-1">Upload Files</div>
                          <div className="flex flex-col gap-2">
                            <div className="flex items-center justify-center w-full border-2 border-dashed border-border rounded-md p-6">
                              <label
                                htmlFor="file-upload"
                                className="flex flex-col items-center gap-2 cursor-pointer"
                              >
                                <Upload className="h-10 w-10 text-muted-foreground" />
                                <span className="text-sm font-medium text-muted-foreground">
                                  {selectedFiles.length > 0
                                    ? `${selectedFiles.length} file(s) selected`
                                    : formData.files &&
                                        formData.files.length > 0
                                      ? "Replace files"
                                      : "Select files to upload"}
                                </span>
                                <input
                                  id="file-upload"
                                  type="file"
                                  multiple
                                  onChange={handleFileChange}
                                  disabled={isUploading}
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
                                        {file.name} (
                                        {(file.size / 1024).toFixed(1)} KB)
                                      </span>
                                    </div>
                                    <Button
                                      type="button"
                                      variant="ghost"
                                      size="icon"
                                      onClick={() =>
                                        setSelectedFiles((prev) =>
                                          prev.filter((_, i) => i !== index),
                                        )
                                      }
                                      className="h-8 w-8"
                                    >
                                      <X className="h-4 w-4" />
                                    </Button>
                                  </div>
                                ))}
                              </div>
                            )}

                            {formData.files &&
                              formData.files.length > 0 &&
                              selectedFiles.length === 0 && (
                                <div className="space-y-2">
                                  {formData.files.map((filePath, index) => (
                                    <div
                                      key={index}
                                      className="flex items-center justify-between p-2 bg-muted rounded-md"
                                    >
                                      <div className="flex items-center gap-2">
                                        <Database className="h-4 w-4" />
                                        <span className="text-sm">
                                          {filePath}
                                        </span>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              )}

                            {isUploading && (
                              <div className="p-2 text-sm text-muted-foreground">
                                Uploading files... Please wait.
                              </div>
                            )}
                          </div>
                        </div>
                      ) : (
                        // --- Data source dropdown block ---
                        <div>
                          <div className="mb-1">Data Source</div>
                          <Select
                            value={formData.sync_source_id || ""}
                            onValueChange={(value) => {
                              if (value === "__create__") {
                                setIsDataSourceDialogOpen(true);
                                return;
                              }
                              setFormData((prev) => ({
                                ...prev,
                                sync_source_id: value,
                              }));
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
                          {/* SharePoint-specific input */}
                          {formData.type === "sharepoint" && (
                            <>
                              <div className="mt-4">
                                <div className="mb-1">SharePoint Site Link</div>
                                <Input
                                  id="url"
                                  name="url"
                                  type="url"
                                  value={formData.url || ""}
                                  onChange={handleInputChange}
                                  placeholder="https://yourcompany.sharepoint.com/sites/..."
                                />
                              </div>
                            </>
                          )}
                          {/* Shared schedule & sync toggle for s3, sharepoint or Network Share */}
                          {[
                            "s3",
                            "sharepoint",
                            "smb_share_folder",
                            "azure_blob",
                            "zendesk",
                          ].includes(formData.type) && (
                            <>
                              <div className="col-span-2 space-y-4">
                                <div className="mt-6">
                                  <div className="bg-gray-50 rounded-lg">
                                    <div className="flex items-center justify-between p-4">
                                      <div>
                                        <div>
                                          <div className="mb-1">
                                            Sync Schedule/Enable
                                          </div>
                                          <Input
                                            id="sync_schedule"
                                            name="sync_schedule"
                                            disabled={
                                              !formData.sync_active && true
                                            }
                                            value={formData.sync_schedule ?? ""}
                                            onChange={(e) => {
                                              const value = e.target.value;
                                              setFormData((prev) => ({
                                                ...prev,
                                                sync_schedule: value,
                                              }));
                                            }}
                                            placeholder="e.g. every 15':  */15 * * * *"
                                          />
                                        </div>
                                      </div>

                                      <div className="flex items-center justify-between mt-2">
                                        <Switch
                                          id="sync_active"
                                          checked={
                                            formData.sync_active || false
                                          }
                                          onCheckedChange={(checked) =>
                                            setFormData((prev) => ({
                                              ...prev,
                                              sync_active: checked,
                                            }))
                                          }
                                        />
                                      </div>
                                    </div>

                                    {/* Extra Processing Options (each on its own row) */}
                                    <div className="space-y-4 p-4 border-t">
                                      {/* Processing Filter */}
                                      <div>
                                        <label className="block text-sm font-medium text-gray-700">
                                          Processing Filter
                                        </label>
                                        <Input
                                          name="processing_filter"
                                          value={
                                            formData.processing_filter || ""
                                          }
                                          onChange={handleInputChange}
                                          placeholder="e.g. *.pdf or contains:report"
                                          className="mt-1"
                                        />
                                      </div>

                                      {/* Processing Mode */}
                                      <div>
                                        <label className="block text-sm font-medium text-gray-700">
                                          Processing Mode
                                        </label>
                                        <Select
                                          value={
                                            formData.processing_mode || "none"
                                          }
                                          onValueChange={(value) =>
                                            setFormData((prev) => ({
                                              ...prev,
                                              processing_mode:
                                                value === "none" ? null : value,
                                            }))
                                          }
                                        >
                                          <SelectTrigger className="mt-1 w-full">
                                            <SelectValue placeholder="None" />
                                          </SelectTrigger>
                                          <SelectContent>
                                            <SelectItem value="none">
                                              None
                                            </SelectItem>
                                            <SelectItem value="extract">
                                              Extract Only
                                            </SelectItem>
                                            <SelectItem value="transcribe">
                                              Transcribe
                                            </SelectItem>
                                          </SelectContent>
                                        </Select>
                                      </div>

                                      {/* TRANSCRIPTION Engine */}
                                      {formData.processing_mode ===
                                        "transcribe" && (
                                        <div>
                                          <label className="block text-sm font-medium text-gray-700">
                                            Transcription Engine
                                          </label>

                                          <Select
                                            value={
                                              formData.transcription_engine
                                            }
                                            onValueChange={(value) =>
                                              setFormData((prev) => ({
                                                ...prev,
                                                transcription_engine: value,
                                              }))
                                            }
                                          >
                                            <SelectTrigger className="mt-1 w-full">
                                              <SelectValue placeholder="Select engine" />
                                            </SelectTrigger>
                                            <SelectContent>
                                              <SelectItem value="openai_whisper">
                                                OpenAI Whisper
                                              </SelectItem>
                                              <SelectItem value="google_chirp3">
                                                Google Chirp 3
                                              </SelectItem>
                                            </SelectContent>
                                          </Select>
                                        </div>
                                      )}

                                      {/* LLM Analyst */}
                                      <div>
                                        <label className="block text-sm font-medium text-gray-700">
                                          LLM Analyst (optional)
                                        </label>
                                        <Select
                                          value={
                                            formData.llm_analyst_id || "none"
                                          }
                                          onValueChange={(value) =>
                                            setFormData((prev) => ({
                                              ...prev,
                                              llm_analyst_id:
                                                value === "none" ? null : value,
                                            }))
                                          }
                                        >
                                          <SelectTrigger className="mt-1 w-full">
                                            <SelectValue placeholder="Select an analyst" />
                                          </SelectTrigger>
                                          <SelectContent>
                                            <SelectItem value="none">
                                              None
                                            </SelectItem>
                                            {llmAnalysts.map((a) => (
                                              <SelectItem
                                                key={a.id}
                                                value={String(a.id)}
                                              >
                                                {a.name}
                                              </SelectItem>
                                            ))}
                                          </SelectContent>
                                        </Select>
                                      </div>

                                      {/* Save in Conversation */}
                                      {formData.processing_mode ===
                                        "transcribe" && (
                                        <div className="flex items-center justify-between">
                                          <label className="text-sm font-medium text-gray-700">
                                            Save In Conversation
                                          </label>

                                          <Switch
                                            checked={
                                              formData.save_in_conversation
                                            }
                                            onCheckedChange={(checked) =>
                                              setFormData((prev) => ({
                                                ...prev,
                                                save_in_conversation: checked,
                                              }))
                                            }
                                          />
                                        </div>
                                      )}

                                      {/* Save Output in source location*/}
                                      <div className="flex items-center gap-4">
                                        <div className="flex items-center gap-2">
                                          <label className="text-sm font-medium text-gray-700 whitespace-nowrap">
                                            Save Output in source location
                                          </label>

                                          <Switch
                                            checked={formData.save_output}
                                            onCheckedChange={(checked) =>
                                              setFormData((prev) => ({
                                                ...prev,
                                                save_output: checked,
                                              }))
                                            }
                                          />
                                        </div>

                                        {formData.save_output && (
                                          <Input
                                            placeholder="Output path (e.g. /storage/out/)"
                                            value={formData.save_output_path}
                                            onChange={(e) =>
                                              setFormData((prev) => ({
                                                ...prev,
                                                save_output_path:
                                                  e.target.value,
                                              }))
                                            }
                                            className="flex-1"
                                          />
                                        )}
                                      </div>
                                    </div>
                                  </div>
                                </div>
                              </div>
                            </>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                <div className="-mx-6 my-0 border-t border-gray-200" />

                <DynamicRagConfigSection
                  ragConfig={dynamicRagConfig}
                  onChange={handleRagConfigChange}
                  showOnlyRequired={true}
                  knowledgeId={editingItem?.id}
                  initialLegraFinalize={Boolean(
                    (editingItem as any)?.legra_finalize,
                  )}
                />
              </div>

              {/* Submit buttons */}
              <div className="flex justify-end gap-3">
                <Button type="button" variant="outline" onClick={handleCancel}>
                  Cancel
                </Button>
                <Button type="submit" disabled={loading || isUploading}>
                  {loading || isUploading
                    ? "Saving..."
                    : editingItem
                      ? "Update Knowledge Base"
                      : "Create Knowledge Base"}
                </Button>
              </div>
            </div>
          </form>
        </>
      ) : (
        <>
          <div className="flex flex-col gap-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-3xl font-bold">Knowledge Base</h2>
                <p className="text-zinc-400 font-normal">
                  View and manage the knowledge base
                </p>
              </div>
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Select
                    value={typeFilter}
                    onValueChange={(value) => setTypeFilter(value)}
                    defaultValue="all"
                  >
                    <SelectTrigger className="min-w-32">
                      <SelectValue placeholder="Filter by type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">(Show all)</SelectItem>
                      <SelectItem value="text">Text</SelectItem>
                      <SelectItem value="file">File</SelectItem>
                      <SelectItem value="url">URL</SelectItem>
                      <SelectItem value="s3">S3</SelectItem>
                      <SelectItem value="sharepoint">Sharepoint</SelectItem>
                      <SelectItem
                        key="smb_share_folder"
                        value="smb_share_folder"
                      >
                        Network Share/Folder
                      </SelectItem>
                      <SelectItem value="azure_blob">
                        Azure Blob Storage
                      </SelectItem>
                      <SelectItem value="google_bucket">
                        Google Bucket Storage
                      </SelectItem>
                      <SelectItem value="zendesk">Zendesk</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="relative">
                  <Search className="absolute top-0 bottom-0 left-3 my-auto text-gray-500 h-4 w-4" />
                  <Input
                    placeholder="Search knowledge base..."
                    className="pl-9 min-w-64"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
                <Button onClick={() => setShowForm(true)}>
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

            {success && (
              <div className="flex items-center gap-2 p-3 text-green-600 bg-green-50 rounded-md">
                <CheckCircle2 className="h-4 w-4" />
                <p className="text-sm font-medium">{success}</p>
              </div>
            )}

            <div className="rounded-lg border bg-white overflow-hidden">
              {loading ? (
                <div className="flex justify-center items-center py-12">
                  <div className="text-sm text-gray-500">
                    Loading knowledge base items...
                  </div>
                </div>
              ) : filteredItems.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 gap-4 text-center">
                  <Database className="h-12 w-12 text-gray-400" />
                  <h3 className="font-medium text-lg">
                    No knowledge base items found
                  </h3>
                  <p className="text-sm text-gray-500 max-w-sm">
                    {searchQuery ? "Try adjusting your search query or" : ""}{" "}
                    add your first knowledge item to start building your
                    knowledge base.
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-gray-100">
                  {filteredItems.map((item) => (
                    <div key={item.id} className="py-4 px-6">
                      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                        <div className="flex-1 flex flex-col space-y-1">
                          <div className="flex items-center gap-2">
                            <h4 className="text-lg font-semibold">
                              {item.name}
                            </h4>
                            <span className="inline-flex items-center rounded-md bg-gray-100 px-2 py-0.5 text-xs font-bold text-black">
                              {item.type.toUpperCase()}
                            </span>
                          </div>
                          <p className="text-sm text-gray-500">
                            {item.description}
                          </p>
                          {item.type === "file" && (
                            <div className="flex items-center text-sm text-gray-500 mt-1">
                              <FileText className="h-4 w-4 mr-1" />
                              <span>
                                {item.files && item.files.length > 0
                                  ? item.files.length === 1
                                    ? item.files[0]
                                    : `${item.files.length} files`
                                  : item.content
                                      .replace("File: ", "")
                                      .replace("Files: ", "")}
                              </span>
                            </div>
                          )}
                          {item.type === "text" && (
                            <p className="text-sm text-gray-500 mt-1 line-clamp-1">
                              {item.content.substring(0, 100)}
                              {item.content.length > 100 ? "..." : ""}
                            </p>
                          )}
                          {item.type === "url" && (
                            <div className="flex items-center text-sm text-gray-500 mt-1">
                              <span>URL: </span>
                              <a
                                href={item.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-blue-600 hover:text-blue-800 underline ml-1 truncate"
                              >
                                {item.url}
                              </a>
                            </div>
                          )}
                        </div>
                        <div className="flex gap-2 justify-center md:justify-end w-full md:w-auto">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleEdit(item)}
                            className="h-8 w-8"
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() =>
                              handleDeleteClick(item.id, item.name)
                            }
                            className="h-8 w-8 text-red-500"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}

      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDelete}
        isInProgress={isDeleting}
        itemName={knowledgeBaseToDelete?.name || ""}
        description={`This action cannot be undone. This will permanently delete knowledge base item "${knowledgeBaseToDelete?.name}".`}
      />

      <DataSourceDialog
        isOpen={isDataSourceDialogOpen}
        onOpenChange={(open) => setIsDataSourceDialogOpen(open)}
        onDataSourceSaved={(created) => {
          if (created?.id) {
            setFormData((prev) => ({ ...prev, sync_source_id: created.id! }));
            // refresh sources
            (async () => {
              const allSources = await getAllDataSources();
              let targetType = formData.type;
              if (formData.type === "sharepoint") targetType = "o365";
              if (formData.type === "zendesk") targetType = "zendesk";
              const filtered = allSources.filter(
                (source) => source.source_type.toLowerCase() === targetType,
              );
              setAvailableSources(filtered);
            })();
          }
        }}
        mode="create"
        defaultSourceType={targetTypes[formData.type]}
        disableSourceType={true}
      />
    </div>
  );
};

export default KnowledgeBaseManager;
