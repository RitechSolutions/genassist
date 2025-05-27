import React, { useState, useEffect } from "react";
import {
  getAllKnowledgeItems,
  createKnowledgeItem,
  updateKnowledgeItem,
  deleteKnowledgeItem,
  uploadFile as apiUploadFile,
} from "@/services/api";
import { v4 as uuidv4 } from "uuid";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Textarea } from "@/components/textarea";
import { Switch } from "@/components/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
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

interface VectorDB {
  enabled: boolean;
  type: string;
  collection_name: string;
  [key: string]: unknown;
}

interface GraphDB {
  enabled: boolean;
  type: string;
  [key: string]: unknown;
}

interface LightRAG {
  enabled: boolean;
  search_mode: string;
  [key: string]: unknown;
}

interface RagConfig {
  enabled: boolean;
  vector_db: VectorDB;
  graph_db: GraphDB;
  light_rag: LightRAG;
  [key: string]: unknown;
}

interface KnowledgeItem {
  id: string;
  name: string;
  description: string;
  content: string;
  type: string;
  file?: string | null;
  rag_config?: RagConfig;
  [key: string]: unknown;
}

const KnowledgeBaseManager: React.FC = () => {
  const [items, setItems] = useState<KnowledgeItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [showForm, setShowForm] = useState<boolean>(false);

  const [typeFilter, setTypeFilter] = useState<string>("text");


  const [editingItem, setEditingItem] = useState<KnowledgeItem | null>(null);
  const [formData, setFormData] = useState<KnowledgeItem>({
    id: uuidv4(),
    name: "",
    description: "",
    content: "",
    type: "text", // Default to text type
    file: null,
    rag_config: {
      enabled: false,
      vector_db: {
        enabled: false,
        type: "chroma",
        collection_name: "",
      },
      graph_db: {
        enabled: false,
        type: "neo4j",
      },
      light_rag: {
        enabled: false,
        search_mode: "mix",
      },
    },
  });

  useEffect(() => {
    fetchItems();
  }, []);

  const fetchItems = async () => {
    try {
      setLoading(true);
      const data = await getAllKnowledgeItems();
      setItems(data);
      setError(null);
    } catch (err) {
      setError("Failed to load knowledge base items");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleRagConfigChange = (updatedRagConfig: RagConfig) => {
    const anyOn =
    Boolean(updatedRagConfig.vector_db?.enabled) ||
    Boolean(updatedRagConfig.graph_db?.enabled) ||
    Boolean(updatedRagConfig.light_rag?.enabled);

    setFormData((prev) => ({
      ...prev,
      rag_config: {
        ...updatedRagConfig,
        enabled: anyOn,
      },
    }));
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    setSelectedFile(file);

    setFormData((prev) => ({
      ...prev,
      file: null,
      content: file ? `File: ${file.name}` : "",
    }));
  };

  const uploadFile = async () => {
    if (!selectedFile) return null;

    setIsUploading(true);

    try {
      const result = await apiUploadFile(selectedFile);
      return result;
    } catch (error) {
      console.error("Error uploading file:", error);
      setError(
        `Failed to upload file: ${
          error instanceof Error ? error.message : String(error)
        }`
      );
      return null;
    } finally {
      setIsUploading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      setLoading(true);
      setError(null);
      setSuccess(null);

      if (!formData.name || !formData.description) {
        throw new Error("Name and description are required");
      }

      if (formData.type === "text" && !formData.content) {
        throw new Error("Content is required for text items");
      }

      if (formData.type === "file" && !selectedFile && !formData.file) {
        throw new Error("Please select a file");
      }

      const dataToSubmit = { ...formData };

      if (formData.type === "file" && selectedFile && !formData.file) {
        const uploadResult = await uploadFile();

        if (!uploadResult) {
          throw new Error("File upload failed");
        }

        dataToSubmit.file = uploadResult.file_path;
        dataToSubmit.content = `File: ${uploadResult.original_filename}`;
      }

      dataToSubmit.rag_config = {
        ...dataToSubmit.rag_config,
        enabled:
          Boolean(dataToSubmit.rag_config.vector_db?.enabled) ||
          Boolean(dataToSubmit.rag_config.graph_db?.enabled) ||
          Boolean(dataToSubmit.rag_config.light_rag?.enabled),
      };
    
      if (editingItem) {
        await updateKnowledgeItem(editingItem.id, dataToSubmit);
        setSuccess(
          `Knowledge base item "${dataToSubmit.name}" updated successfully`
        );
      } else {
        if (!dataToSubmit.id) {
          dataToSubmit.id = uuidv4();
        }
        await createKnowledgeItem(dataToSubmit);
        setSuccess(
          `Knowledge base item "${dataToSubmit.name}" created successfully`
        );
      }

      setFormData({
        id: uuidv4(),
        name: "",
        description: "",
        content: "",
        type: "text",
        file: null,
        rag_config: {
          enabled: false,
          vector_db: {
            enabled: false,
            type: "chroma",
            collection_name: "",
          },
          graph_db: {
            enabled: false,
            type: "neo4j",
          },
          light_rag: {
            enabled: false,
            search_mode: "mix",
          },
        },
      });
      setSelectedFile(null);
      setEditingItem(null);
      setShowForm(false);
      fetchItems();
    } catch (err) {
      setError(
        `Failed to ${editingItem ? "update" : "create"} knowledge base item: ${
          err instanceof Error ? err.message : String(err)
        }`
      );
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    setFormData({
      id: uuidv4(),
      name: "",
      description: "",
      content: "",
      type: "text",
      file: null,
      rag_config: {
        enabled: false,
        vector_db: {
          enabled: false,
          type: "chroma",
          collection_name: "",
        },
        graph_db: {
          enabled: false,
          type: "neo4j",
        },
        light_rag: {
          enabled: false,
          search_mode: "mix",
        },
      },
    });
    setSelectedFile(null);
    setEditingItem(null);
    setError(null);
    setSuccess(null);
    setShowForm(false);
  };

  const handleEdit = (item: KnowledgeItem) => {
    setEditingItem(item);

    const lightRagConfig = item.rag_config?.light_rag || {
      enabled: false,
      search_mode: "mix",
    };

    setFormData({
      id: item.id,
      name: item.name,
      description: item.description,
      content: item.content,
      type: item.type || "text",
      file: item.file || null,
      rag_config: {
        enabled: item.rag_config?.enabled || false,
        vector_db: item.rag_config?.vector_db || {
          enabled: false,
          type: "chroma",
          collection_name: "",
        },
        graph_db: item.rag_config?.graph_db || {
          enabled: false,
          type: "neo4j",
        },
        light_rag: lightRagConfig,
      },
    });
    setSelectedFile(null);
    setShowForm(true);
  };

  const handleDelete = async (id: string, name: string) => {
    if (window.confirm(`Are you sure you want to delete "${name}"?`)) {
      try {
        setLoading(true);
        await deleteKnowledgeItem(id);
        setSuccess(`Knowledge base item "${name}" deleted successfully`);
        fetchItems();
      } catch (err) {
        setError(
          `Failed to delete knowledge base item: ${
            err instanceof Error ? err.message : String(err)
          }`
        );
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
  };

  // const filteredItems = items.filter((item) => {
  //   return (
  //     item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
  //     item.description.toLowerCase().includes(searchQuery.toLowerCase())
  //   );
  // });
  const filteredItems = items.filter((item) => {
    const matchesQuery =
      item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.description.toLowerCase().includes(searchQuery.toLowerCase());

    return matchesQuery && item.type === typeFilter;
  });


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
                  <div className="grid grid-cols-3 gap-6">
                    <div>
                      <h3 className="text-lg font-semibold">Basic Information</h3>
                      <p className="text-sm text-gray-500 mt-1">
                        Basic information about the knowledge base.
                      </p>
                    </div>
                    
                    <div className="col-span-2 space-y-6">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <div className="mb-1">Name</div>
                          <Input
                            id="name"
                            name="name"
                            value={formData.name}
                            onChange={handleInputChange}
                            placeholder="Name for this knowledge base item"
                            required
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
                            required
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
                            <SelectItem value="s3">S3</SelectItem>
                            <SelectItem value="database">Database</SelectItem>
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
                            required
                            className="min-h-32"
                          />
                        </div>
                      ) : (
                        <div>
                          <div className="mb-1">Upload File</div>
                          <div className="flex flex-col gap-2">
                            <div className="flex items-center justify-center w-full border-2 border-dashed border-border rounded-md p-6">
                              <label
                                htmlFor="file-upload"
                                className="flex flex-col items-center gap-2 cursor-pointer"
                              >
                                <Upload className="h-10 w-10 text-muted-foreground" />
                                <span className="text-sm font-medium text-muted-foreground">
                                  {selectedFile
                                    ? selectedFile.name
                                    : formData.file
                                    ? "Replace file"
                                    : "Select file to upload"}
                                </span>
                                <input
                                  id="file-upload"
                                  type="file"
                                  onChange={handleFileChange}
                                  disabled={isUploading}
                                  className="hidden"
                                />
                              </label>
                            </div>

                            {selectedFile && (
                              <div className="flex items-center justify-between p-2 bg-muted rounded-md">
                                <div className="flex items-center gap-2">
                                  <FilePlus className="h-4 w-4" />
                                  <span className="text-sm">
                                    {selectedFile.name} (
                                    {(selectedFile.size / 1024).toFixed(1)} KB)
                                  </span>
                                </div>
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => setSelectedFile(null)}
                                  className="h-8 w-8"
                                >
                                  <X className="h-4 w-4" />
                                </Button>
                              </div>
                            )}

                            {formData.file && !selectedFile && (
                              <div className="flex items-center justify-between p-2 bg-muted rounded-md">
                                <div className="flex items-center gap-2">
                                  <Database className="h-4 w-4" />
                                  <span className="text-sm">
                                    File: {formData.file}
                                  </span>
                                </div>
                              </div>
                            )}

                            {isUploading && (
                              <div className="p-2 text-sm text-muted-foreground">
                                Uploading file... Please wait.
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                <div className="-mx-6 my-0 border-t border-gray-200" />

                {/* RAG Configuration */}
                <div className="p-6">
                  <div className="grid grid-cols-3 gap-6">
                    <div>
                      <h3 className="text-lg font-semibold">RAG</h3>
                      <p className="text-sm text-gray-500 mt-1">
                        Configure Retrieval Augmented Generation settings
                      </p>
                    </div>
                    
                    <div className="col-span-2 space-y-4">
                      <div className="bg-gray-50 rounded-lg">
                        <div className="flex items-center justify-between p-4">
                          <div className="flex items-center gap-2">
                            <Database className="h-5 w-5 text-gray-500" />
                            <div>
                              <div className="font-medium">Vector Database</div>
                              <p className="text-sm text-gray-500">Enable vector database for this knowledge item</p>
                            </div>
                          </div>
                          <Switch
                            checked={formData.rag_config?.vector_db?.enabled || false}
                            onCheckedChange={(checked) => {
                              const updatedRagConfig = {
                                ...formData.rag_config!,
                                vector_db: {
                                  ...formData.rag_config!.vector_db,
                                  enabled: checked
                                }
                              };
                              handleRagConfigChange(updatedRagConfig);
                            }}
                          />
                        </div>
                        
                        {formData.rag_config?.vector_db?.enabled && (
                          <div className="p-4 pt-0 space-y-4">
                            <div>
                              <div className="mb-1">Vector DB Type</div>
                              <Select
                                value={formData.rag_config?.vector_db?.type || "chroma"}
                                onValueChange={(value) => {
                                  const updatedRagConfig = {
                                    ...formData.rag_config!,
                                    vector_db: {
                                      ...formData.rag_config!.vector_db,
                                      type: value
                                    }
                                  };
                                  handleRagConfigChange(updatedRagConfig);
                                }}
                              >
                                <SelectTrigger>
                                  <SelectValue placeholder="Select vector database type" />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="chroma">Chroma</SelectItem>
                                  <SelectItem value="pinecone">Pinecone</SelectItem>
                                  <SelectItem value="qdrant">Qdrant</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                            
                            <div>
                              <div className="mb-1">Collection Name</div>
                              <Input
                                placeholder="Default: agent_id_collection"
                                value={formData.rag_config?.vector_db?.collection_name || ""}
                                onChange={(e) => {
                                  const updatedRagConfig = {
                                    ...formData.rag_config!,
                                    vector_db: {
                                      ...formData.rag_config!.vector_db,
                                      collection_name: e.target.value
                                    }
                                  };
                                  handleRagConfigChange(updatedRagConfig);
                                }}
                              />
                            </div>
                          </div>
                        )}
                      </div>
                      
                      <div className="bg-gray-50 rounded-lg">
                        <div className="flex items-center justify-between p-4">
                          <div className="flex items-center gap-2">
                            <FileText className="h-5 w-5 text-gray-500" />
                            <div>
                              <div className="font-medium">LightRAG</div>
                              <p className="text-sm text-gray-500">Enable lightweight RAG for this knowledge item</p>
                            </div>
                          </div>
                          <Switch
                            checked={formData.rag_config?.light_rag?.enabled || false}
                            onCheckedChange={(checked) => {
                              const updatedRagConfig = {
                                ...formData.rag_config!,
                                light_rag: {
                                  ...formData.rag_config!.light_rag,
                                  enabled: checked
                                }
                              };
                              handleRagConfigChange(updatedRagConfig);
                            }}
                          />
                        </div>
                        
                        {formData.rag_config?.light_rag?.enabled && (
                          <div className="p-4 pt-0 space-y-2">
                            <div>
                              <div className="mb-1">Search Mode</div>
                              <Select
                                value={formData.rag_config?.light_rag?.search_mode || "mix"}
                                onValueChange={(value) => {
                                  const updatedRagConfig = {
                                    ...formData.rag_config!,
                                    light_rag: {
                                      ...formData.rag_config!.light_rag,
                                      search_mode: value
                                    }
                                  };
                                  handleRagConfigChange(updatedRagConfig);
                                }}
                              >
                                <SelectTrigger>
                                  <SelectValue placeholder="Select search mode" />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="mix">Mix (Recommended)</SelectItem>
                                  <SelectItem value="vector">Vector Only</SelectItem>
                                  <SelectItem value="keyword">Keyword Only</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                            
                            <p className="text-sm text-gray-500 mt-4">
                              Mix mode integrates knowledge graph and vector retrieval for best results.
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Submit buttons */}
              <div className="flex justify-end gap-3">
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleCancel}
                >
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
                  <Select value={typeFilter} onValueChange={(value) => setTypeFilter(value)} defaultValue="text">
                    <SelectTrigger className="min-w-32">
                      <SelectValue placeholder="Filter by type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="text">Text</SelectItem>
                      <SelectItem value="file">File</SelectItem>
                      <SelectItem value="s3">S3</SelectItem>
                      <SelectItem value="database">Database</SelectItem>
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
                              {item.type === "file" ? "FILE" : "TEXT"}
                            </span>
                          </div>
                          <p className="text-sm text-gray-500">
                            {item.description}
                          </p>
                          {item.type === "file" && (
                            <div className="flex items-center text-sm text-gray-500 mt-1">
                              <FileText className="h-4 w-4 mr-1" />
                              <span>
                                {item.file ||
                                  item.content.replace("File: ", "")}
                              </span>
                            </div>
                          )}
                          {item.type === "text" && (
                            <p className="text-sm text-gray-500 mt-1 line-clamp-1">
                              {item.content.substring(0, 100)}
                              {item.content.length > 100 ? "..." : ""}
                            </p>
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
                            onClick={() => handleDelete(item.id, item.name)}
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
    </div>
  );
};

export default KnowledgeBaseManager;
