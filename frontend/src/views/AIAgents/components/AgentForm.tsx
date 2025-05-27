import React, { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  createAgentConfig,
  getAgentConfig,
  updateAgentConfig,
  getAllKnowledgeItems,
} from "@/services/api";
import { getAllTools } from "@/services/tools";
import { getAllLLMProviders } from "@/services/llmProviders";
import { LLMProvider } from "@/interfaces/llmProvider.interface";
import { Tool } from "@/interfaces/tool.interface";
import { v4 as uuidv4 } from "uuid";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Textarea } from "@/components/textarea";
import { Label } from "@/components/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Checkbox } from "@/components/checkbox";
import {
  ChevronLeft,
  AlertCircle,
  CheckCircle2,
  Check,
  Trash2,
} from "lucide-react";

interface AgentFormData {
  id?: string;
  name: string;
  description: string;
  llm_provider_id: string;
  system_prompt: string;
  knowledge_base_ids: string[];
  tool_ids: string[];
  settings: Record<string, unknown>;
  is_active: boolean;
  email: string;
  welcome_message: string;
  possible_queries: string[];
  [key: string]: unknown;
}

interface KnowledgeItem {
  id: string;
  name: string;
  description?: string;
  type?: string;
  rag_config?: {
    enabled: boolean;
  };
  [key: string]: unknown;
}

const AgentForm: React.FC = () => {
  const { agentId } = useParams<{ agentId: string }>();
  const id = agentId;

  const navigate = useNavigate();
  const isEditMode = !!id;

  const [formData, setFormData] = useState<AgentFormData>({
    id: isEditMode ? id : undefined,
    name: "",
    description: "",
    llm_provider_id: "",
    system_prompt: "",
    knowledge_base_ids: [],
    tool_ids: [],
    settings: {},
    is_active: false,
    email: "",
    welcome_message: "Welcome",
    possible_queries: ["What can you do?"],
  });

  const [knowledgeItems, setKnowledgeItems] = useState<KnowledgeItem[]>([]);
  const [tools, setTools] = useState<Tool[]>([]);
  const [llmProviders, setLlmProviders] = useState<LLMProvider[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<boolean>(false);
  const [selectedLLMProvider, setSelectedLLMProvider] = useState<LLMProvider | null>(null);

  useEffect(() => {
    const fetchKnowledgeItems = async () => {
      try {
        const items = await getAllKnowledgeItems();
        setKnowledgeItems(items);
      } catch (err) {
        console.error("Failed to load knowledge base items:", err);
      }
    };

    const fetchTools = async () => {
      try {
        const items = await getAllTools();
        setTools(items);
      } catch (err) {
        console.error("Failed to load tools:", err);
      }
    };

    const fetchLLMProviders = async () => {
      try {
        const providers = await getAllLLMProviders();
        setLlmProviders(providers);
      } catch (err) {
        console.error("Failed to load LLM providers:", err);
      }
    };

    fetchKnowledgeItems();
    fetchTools();
    fetchLLMProviders();
    
    if (isEditMode) {
      const fetchAgentConfig = async () => {
        try {
          setLoading(true);
          const config = await getAgentConfig(id);
          
          const cleanedQueries = config.possible_queries?.filter(q => q.trim() !== '');
          
          setFormData({
            ...config,
            possible_queries: cleanedQueries.length > 0 ? cleanedQueries : []
          });
          
          setError(null);
        } catch (err) {
          setError("Failed to load agent configuration");
          console.error(err);
        } finally {
          setLoading(false);
        }
      };

      fetchAgentConfig();
    }
  }, [id, isEditMode]);

  useEffect(() => {
    if (formData.llm_provider_id && llmProviders.length > 0) {
      const provider = llmProviders.find(p => p.id === formData.llm_provider_id);
      setSelectedLLMProvider(provider || null);
    }
  }, [formData.llm_provider_id, llmProviders]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement> | { target: { name: string; value: string | boolean | string[] } }) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handlePossibleQueryChange = (index: number, value: string) => {
    setFormData((prev) => {
      const queries = [...prev.possible_queries];
      queries[index] = value;
      return {
        ...prev,
        possible_queries: queries,
      };
    });
  };

  const addPossibleQuery = () => {
    setFormData((prev) => ({
      ...prev,
      possible_queries: [...prev.possible_queries, ""],
    }));
  };

  const removePossibleQuery = (index: number) => {
    setFormData((prev) => {
      const queries = [...prev.possible_queries];
      queries.splice(index, 1);
      return {
        ...prev,
        possible_queries: queries,
      };
    });
  };

  const handleKnowledgeBaseChange = (itemId: string, checked: boolean) => {
    setFormData((prev) => {
      const currentIds = [...prev.knowledge_base_ids];

      if (checked) {
        if (!currentIds.includes(itemId)) {
          currentIds.push(itemId);
        }
      } else {
        const index = currentIds.indexOf(itemId);
        if (index !== -1) {
          currentIds.splice(index, 1);
        }
      }

      return {
        ...prev,
        knowledge_base_ids: currentIds,
      };
    });
  };

  const handleToolChange = (toolId: string, checked: boolean) => {
    setFormData((prev) => {
      const currentIds = [...(prev.tool_ids || [])];

      if (checked) {
        if (!currentIds.includes(toolId)) {
          currentIds.push(toolId);
        }
      } else {
        const index = currentIds.indexOf(toolId);
        if (index !== -1) {
          currentIds.splice(index, 1);
        }
      }

      return {
        ...prev,
        tool_ids: currentIds,
      };
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      setLoading(true);

      if (isEditMode) {
        const { id: _, ...dataToSubmit } = formData;
        await updateAgentConfig(id, dataToSubmit);
        setSuccess(true);
      } else {
        const { id: _, ...dataToSubmit } = formData;
        await createAgentConfig(dataToSubmit);
        navigate("/ai-agents");
      }

      setError(null);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
      setError(
        `Failed to ${isEditMode ? "update" : "create"} agent. ${errorMessage}`
      );
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate("/ai-agents")}
          className="mr-2"
        >
          <ChevronLeft className="h-5 w-5" />
        </Button>
        <h2 className="text-2xl font-bold tracking-tight">
          {isEditMode ? "Edit Agent" : "Create New Agent"}
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
          <p className="text-sm font-medium">
            Agent successfully {isEditMode ? "updated" : "created"}!
          </p>
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
                    Basic information about agent.
                  </p>
                </div>
                
                <div className="col-span-2 space-y-6">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="mb-1">Agent Name</div>
                      <Input
                        id="name"
                        name="name"
                        value={formData.name}
                        onChange={handleInputChange}
                        placeholder="Enter agent name"
                        required
                      />
                    </div>
                    
                    <div>
                      <div className="mb-1">LLM Provider</div>
                      {llmProviders.length > 0 && (
                        <Select
                          value={formData.llm_provider_id}
                          onValueChange={(value) =>
                            handleInputChange({ target: { name: "llm_provider_id", value } })
                          }
                          defaultValue={formData.llm_provider_id}
                        >
                          <SelectTrigger id="llm_provider_id" className="w-full">
                            <SelectValue placeholder="Select LLM provider" />
                          </SelectTrigger>
                          <SelectContent>
                            {llmProviders.map((provider) => (
                              <SelectItem key={provider.id} value={provider.id}>
                                {provider.name} ({provider.llm_type})
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}
                      {llmProviders.length === 0 && (
                        <div className="text-sm text-gray-500 border rounded p-2">
                          Loading..
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className={isEditMode ? "col-span-2" : ""}>
                      <div className="mb-1">Description</div>
                      <Input
                        id="description"
                        name="description"
                        value={formData.description}
                        onChange={handleInputChange}
                        placeholder="Enter agent description"
                        required
                      />
                    </div>
                    
                    {!isEditMode && (
                      <div>
                        <div className="mb-1">Email</div>
                        <Input
                          id="email"
                          name="email"
                          value={formData.email}
                          onChange={handleInputChange}
                          placeholder="Enter contact email"
                          required
                        />
                      </div>
                    )}
                  </div>

                  <div>
                    <div className="mb-1">System Prompt</div>
                    <Textarea
                      id="system_prompt"
                      name="system_prompt"
                      value={formData.system_prompt}
                      onChange={handleInputChange}
                      placeholder="Enter system prompt"
                      className="min-h-[100px] resize-y"
                      style={{ height: 'auto', minHeight: '100px', maxHeight: '300px' }}
                      rows={Math.max(4, Math.min(12, formData.system_prompt.split('\n').length + 2))}
                      required
                    />
                  </div>

                  <div>
                    <div className="mb-1">Welcome Message</div>
                    <Input
                      id="welcome_message"
                      name="welcome_message"
                      value={formData.welcome_message}
                      onChange={handleInputChange}
                      placeholder="Enter welcome message"
                      required
                    />
                  </div>

                  <div>
                    <div className="mb-1">Frequently Asked Question</div>
                    <div className="space-y-2">
                      {formData.possible_queries.map((query, index) => (
                        <div key={index} className="flex items-center gap-2">
                          <Input
                            value={query}
                            onChange={(e) => handlePossibleQueryChange(index, e.target.value)}
                            placeholder="Enter a sample query"
                          />
                          <Button 
                            type="button" 
                            variant="ghost" 
                            size="icon"
                            onClick={() => removePossibleQuery(index)}
                            disabled={formData.possible_queries.length <= 1}
                            className="px-2 h-9"
                          >
                            <Trash2 className="h-4 w-4 text-red-500" />
                          </Button>
                        </div>
                      ))}
                      <Button
                        type="button"
                        onClick={addPossibleQuery}
                        className="w-full"
                      >
                        Add FAQ
                      </Button>
                    </div>
                  </div>
                  
                  
                </div>
              </div>
            </div>

            <div className="-mx-6 my-0 border-t border-gray-200" />

            {/* Tools Section */}
            <div className="p-6">
              <div className="grid grid-cols-3 gap-6">
                <div>
                  <h3 className="text-lg font-semibold">Tools</h3>
                  <p className="text-sm text-gray-500 mt-1">
                    Choose tools to be used by agent.
                  </p>
                </div>
                
                <div className="col-span-2">
                  {tools.length === 0 ? (
                    <div className="rounded-md bg-gray-50 p-4 text-center">
                      <p className="text-sm text-gray-500">
                        No tools available.{" "}
                        <a href="/tools" className="text-primary underline">
                          Create some first
                        </a>
                        .
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {tools.map((tool) => (
                        <div key={tool.id} className="flex items-start gap-3">
                          <div 
                            className={`w-4 h-4 mt-1 border ${formData.tool_ids?.includes(tool.id) ? 'bg-primary border-primary' : 'bg-white border-gray-300'} flex items-center justify-center`}
                            onClick={() => handleToolChange(tool.id, !formData.tool_ids?.includes(tool.id))}
                          >
                            {formData.tool_ids?.includes(tool.id) && (
                              <Check className="h-3 w-3 text-white" />
                            )}
                          </div>
                          <div className="flex-1">
                            <label
                              className="font-medium text-sm flex items-center gap-2 cursor-pointer"
                              onClick={() => handleToolChange(tool.id, !formData.tool_ids?.includes(tool.id))}
                            >
                              {tool.name}
                              <span className="inline-flex items-center rounded-md bg-gray-100 px-2 py-0.5 text-xs font-bold text-black">
                                {tool.type?.toUpperCase() || "API"}
                              </span>
                            </label>
                            <p className="text-sm text-gray-500 mt-1">{tool.description}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="-mx-6 my-0 border-t border-gray-200" />

            {/* Knowledge Base Section */}
            <div className="p-6">
              <div className="grid grid-cols-3 gap-6">
                <div>
                  <h3 className="text-lg font-semibold">Knowledge Base</h3>
                  <p className="text-sm text-gray-500 mt-1">
                    Choose tools to be used by agent.
                  </p>
                </div>
                
                <div className="col-span-2">
                  {knowledgeItems.length === 0 ? (
                    <div className="rounded-md bg-gray-50 p-4 text-center">
                      <p className="text-sm text-gray-500">
                        No knowledge base items available.{" "}
                        <a href="/knowledge-base" className="text-primary underline">
                          Create some first
                        </a>
                        .
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {knowledgeItems.map((item) => (
                        <div key={item.id} className="flex items-start gap-3">
                          <div 
                            className={`w-4 h-4 mt-1 border ${formData.knowledge_base_ids.includes(item.id) ? 'bg-primary border-primary' : 'bg-white border-gray-300'} flex items-center justify-center`}
                            onClick={() => handleKnowledgeBaseChange(item.id, !formData.knowledge_base_ids.includes(item.id))}
                          >
                            {formData.knowledge_base_ids.includes(item.id) && (
                              <Check className="h-3 w-3 text-white" />
                            )}
                          </div>
                          <div className="flex-1">
                            <label
                              className="font-medium text-sm flex items-center gap-2 cursor-pointer"
                              onClick={() => handleKnowledgeBaseChange(item.id, !formData.knowledge_base_ids.includes(item.id))}
                            >
                              {item.name}
                              <span className="inline-flex items-center rounded-md bg-gray-100 px-2 py-0.5 text-xs font-bold text-black">
                                {item.type?.toUpperCase() || "TEXT"}
                              </span>
                            </label>
                            <p className="text-sm text-gray-500 mt-1">{item.description}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Submit buttons */}
          <div className="flex justify-end gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={() => navigate("/ai-agents")}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading
                ? "Saving..."
                : isEditMode
                ? "Update Agent"
                : "Create Agent"}
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
  
};

export default AgentForm; 