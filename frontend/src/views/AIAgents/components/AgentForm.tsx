import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "react-hot-toast";
import {
  createAgentConfig,
  getAgentConfig,
  updateAgentConfig,
  uploadWelcomeImage,
  getWelcomeImage,
  deleteWelcomeImage,
} from "@/services/api";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Switch } from "@/components/switch";
import { ChevronLeft, AlertCircle, CheckCircle2, Trash2 } from "lucide-react";
// import { createWorkflow, updateWorkflow } from "@/services/workflows";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/sheet";
import { Textarea } from "@/components/textarea";

interface AgentFormData {
  id?: string;
  name: string;
  description: string;
  welcome_message?: string;
  welcome_title?: string;
  thinking_phrase_delay?: number;
  possible_queries?: string[];
  thinking_phrases?: string[];
  is_active?: boolean;
  workflow_id?: string;
  token_based_auth?: boolean;
}

interface AgentFormProps {
  data?: AgentFormData;
  plain?: boolean;
  onClose?: () => void;
  // When true, navigate to workflow after creating an agent
  redirectOnCreate?: boolean;
  onCreated?: (agentId: string) => void;
  // When true, hides internal buttons (for external rendering)
  hideButtons?: boolean;
  // Form ID for external button association
  formId?: string;
}

const AgentForm: React.FC<AgentFormProps> = ({
  data,
  plain = false,
  onClose,
  redirectOnCreate = true,
  onCreated,
  hideButtons = false,
  formId,
}: AgentFormProps) => {
  const id = data?.id;
  const navigate = useNavigate();
  const isEditMode = !!id;
  const cleanedQueries =
    data?.possible_queries?.filter((q) => q.trim() !== "") ?? [];
  const cleanedThinkingPhrases =
    data?.thinking_phrases?.filter((p) => p.trim() !== "") ?? [];

    console.log(data);
  const [formData, setFormData] = useState<AgentFormData>({
    ...(data || {
      name: "",
      description: "",
      welcome_message: "",
      welcome_title: "",
      thinking_phrase_delay: 0,
      possible_queries: [],
      thinking_phrases: [],
      token_based_auth: false,
    }),
    possible_queries: cleanedQueries.length > 0 ? cleanedQueries : [],
    thinking_phrases:
      cleanedThinkingPhrases.length > 0 ? cleanedThinkingPhrases : [],
    token_based_auth: data?.token_based_auth ?? false,
  });

  const [loading, setLoading] = useState<boolean>(false);
  const [success, setSuccess] = useState<boolean>(false);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [imageLoading, setImageLoading] = useState<boolean>(false);
  const [imageDeleting, setImageDeleting] = useState<boolean>(false);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);

  // Load existing image when editing
  React.useEffect(() => {
    const loadExistingImage = async () => {
      if (isEditMode && id) {
        try {
          const imageBlob = await getWelcomeImage(id);
          const imageUrl = URL.createObjectURL(imageBlob);
          setImagePreview(imageUrl);
        } catch (error) {
          // Image doesn't exist or failed to load, which is fine
        }
      }
    };

    loadExistingImage();
  }, [isEditMode, id]);

  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: name === "thinking_phrase_delay" ? Number(value) || 0 : value,
    }));
  };

  const handleSwitchChange = (checked: boolean) => {
    setFormData((prev) => ({
      ...prev,
      token_based_auth: checked,
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

  const handleThinkingPhraseChange = (index: number, value: string) => {
    setFormData((prev) => {
      const phrases = [...prev.thinking_phrases];
      phrases[index] = value;
      return {
        ...prev,
        thinking_phrases: phrases,
      };
    });
  };

  const addThinkingPhrase = () => {
    setFormData((prev) => ({
      ...prev,
      thinking_phrases: [...prev.thinking_phrases, ""],
    }));
  };

  const removeThinkingPhrase = (index: number) => {
    setFormData((prev) => {
      const phrases = [...prev.thinking_phrases];
      phrases.splice(index, 1);
      return {
        ...prev,
        thinking_phrases: phrases,
      };
    });
  };

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      processFile(file);
    }
  };

  const handleRemoveImage = async () => {
    setImageDeleting(true);

    try {
      setImageFile(null);
      setImagePreview(null);

      // If we're in edit mode and there was an existing image, delete it from the server
      if (isEditMode && id) {
        await deleteWelcomeImage(id);
        toast.success("Welcome image removed successfully.");
      }
    } catch (error) {
      // Don't show error toast since the image might not exist
    } finally {
      setImageDeleting(false);
    }
  };

  const processFile = (file: File) => {
    // Validate file type
    if (!file.type.startsWith("image/")) {
      toast.error("Please select an image file.");
      return;
    }

    // Validate file size (5MB max)
    if (file.size > 5 * 1024 * 1024) {
      toast.error("Image file too large. Maximum size is 5MB.");
      return;
    }

    setImageFile(file);

    // Create preview
    const reader = new FileReader();
    reader.onload = (e) => {
      setImagePreview(e.target?.result as string);
    };
    reader.readAsDataURL(file);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      processFile(files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const requiredFields = [
      { label: "Name", isEmpty: !formData.name },
      { label: "Description", isEmpty: !formData.description },
      { label: "Welcome Message", isEmpty: !formData.welcome_message },
    ];

    const missingFields = requiredFields
      .filter((field) => field.isEmpty)
      .map((field) => field.label);

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
      let agentId: string;

      if (isEditMode) {
        const { id: _, ...dataToSubmit } = formData;
        await updateAgentConfig(id, dataToSubmit);
        agentId = id;
        setSuccess(true);
        onClose?.();
      } else {
        const { id: _, ...dataToSubmit } = formData;
        const agentConfig = await createAgentConfig({
          ...dataToSubmit,
        });
        agentId = agentConfig.id;

        // Notify parent about the newly created agent
        onCreated?.(agentId);

        if (redirectOnCreate) {
          navigate(`/ai-agents/workflow/${agentConfig.id}`);
        } else {
          // When redirect is disabled, mark success and let the parent handle next steps.
          setSuccess(true);
          onClose?.();
        }
      }

      // Upload image if provided
      if (imageFile && agentId) {
        setImageLoading(true);
        try {
          await uploadWelcomeImage(agentId, imageFile);
          toast.success("Welcome image uploaded successfully.");
        } catch (error) {
          toast.error("Failed to upload welcome image.");
        } finally {
          setImageLoading(false);
        }
      }

      toast.success(
        `Workflow ${isEditMode ? "updated" : "created"} successfully.`
      );
    } catch (err: unknown) {
      let errorMessage =
        err instanceof Error ? err.message : "Unknown error occurred.";

      if (
        (errorMessage.includes("email") && errorMessage.includes("exist")) ||
        errorMessage.includes("400")
      )
        errorMessage = "An agent with this name already exists.";

      toast.error(
        `Failed to ${isEditMode ? "update" : "create"} agent: ${errorMessage}`
      );

    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {success && (
        <div className="flex items-center gap-2 p-3 text-green-600 bg-green-50 rounded-md">
          <CheckCircle2 className="h-4 w-4" />
          <p className="text-sm font-medium">
            Agent successfully {isEditMode ? "updated" : "created"}!
          </p>
        </div>
      )}

      <form onSubmit={handleSubmit} id={formId}>
        <div className="space-y-6">
          <div className={`${plain ? "" : "rounded-lg border bg-white p-6 "}`}>
            <div className="space-y-6">
              <div>
                <div className="mb-1">Workflow Name</div>
                <Input
                  id="name"
                  name="name"
                  value={formData.name}
                  onChange={handleInputChange}
                  placeholder="Enter agent name"
                />
              </div>

              <div>
                <div className="mb-1">Description</div>
                <Input
                  id="description"
                  name="description"
                  value={formData.description}
                  onChange={handleInputChange}
                  placeholder="Enter agent description"
                />
              </div>
              <div>
                <div className="mb-2 text-sm font-medium text-foreground">Welcome Image</div>
                <div className="space-y-3">
                  {!imagePreview ? (
                    <div className="relative group">
                      <input
                        id="welcome_image"
                        name="welcome_image"
                        type="file"
                        accept="image/*"
                        onChange={handleImageChange}
                        className="hidden"
                      />
                      <label
                        htmlFor="welcome_image"
                        className={`relative flex flex-col items-center justify-center w-full p-8 border-2 border-dashed rounded-xl transition-all duration-200 cursor-pointer overflow-hidden ${
                          isDragOver
                            ? "border-primary bg-primary/10 shadow-lg shadow-primary/20 scale-[1.02]"
                            : "border-border bg-gradient-to-br from-muted/30 to-muted/10 hover:border-primary/50 hover:bg-primary/5 hover:shadow-md"
                        }`}
                        onDragOver={handleDragOver}
                        onDragLeave={handleDragLeave}
                        onDrop={handleDrop}
                      >
                        {/* Background decoration */}
                        <div className="absolute inset-0 bg-grid-pattern opacity-[0.02]"></div>
                        
                        <div className="relative flex flex-col items-center justify-center z-10">
                          {/* Upload icon with cloud */}
                          <div
                            className={`relative w-16 h-16 rounded-2xl flex items-center justify-center mb-4 transition-all duration-300 ${
                              isDragOver 
                                ? "bg-primary/20 scale-110 shadow-lg shadow-primary/30" 
                                : "bg-primary/10 group-hover:bg-primary/15 group-hover:scale-105"
                            }`}
                          >
                            <svg
                              className={`w-8 h-8 transition-all duration-300 ${
                                isDragOver ? "text-primary scale-110" : "text-primary/80 group-hover:text-primary"
                              }`}
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                              xmlns="http://www.w3.org/2000/svg"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                              />
                            </svg>
                            {/* Animated ring on drag */}
                            {isDragOver && (
                              <div className="absolute inset-0 rounded-2xl border-2 border-primary animate-ping opacity-50"></div>
                            )}
                          </div>

                          {/* Text content */}
                          <div className="text-center space-y-1.5">
                            <p
                              className={`text-base font-semibold transition-colors duration-200 ${
                                isDragOver ? "text-primary" : "text-foreground/90 group-hover:text-primary"
                              }`}
                            >
                              {isDragOver ? "Drop your image here" : "Choose a file or drag & drop"}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              Click to select or drag and drop
                            </p>
                            <div className="flex items-center justify-center gap-2 pt-2">
                              <span className="inline-flex items-center px-2.5 py-1 rounded-md bg-background/80 border text-xs font-medium text-muted-foreground">
                                PNG, JPG, GIF
                              </span>
                              <span className="text-xs text-muted-foreground">•</span>
                              <span className="inline-flex items-center px-2.5 py-1 rounded-md bg-background/80 border text-xs font-medium text-muted-foreground">
                                up to 5MB
                              </span>
                            </div>
                          </div>
                        </div>
                      </label>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {/* Image preview card */}
                      <div className="relative group border rounded-xl p-4 bg-gradient-to-br from-muted/30 to-muted/10 hover:shadow-md transition-all duration-200">
                        <div className="flex items-start gap-4">
                          {/* Thumbnail */}
                          <div className="relative shrink-0">
                            <img
                              src={imagePreview}
                              alt="Welcome image preview"
                              className="h-20 w-20 object-cover rounded-lg border-2 border-border shadow-sm ring-2 ring-background"
                            />
                            <Button
                              type="button"
                              variant="destructive"
                              size="icon"
                              onClick={handleRemoveImage}
                              disabled={imageDeleting}
                              className="absolute -top-2 -right-2 h-7 w-7 rounded-full shadow-lg opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                              {imageDeleting ? (
                                <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-white"></div>
                              ) : (
                                <Trash2 className="h-3.5 w-3.5" />
                              )}
                            </Button>
                          </div>
                          
                          {/* File info */}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-start justify-between gap-2">
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-foreground truncate mb-1">
                                  {imageFile?.name || "Welcome image"}
                                </p>
                                {imageFile && (
                                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                    <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-background/80 border font-medium">
                                      {(imageFile.size / 1024 / 1024).toFixed(2)} MB
                                    </span>
                                    <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-green-50 border border-green-200 text-green-700 font-medium">
                                      <CheckCircle2 className="h-3 w-3 mr-1" />
                                      Ready
                                    </span>
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* Replace button */}
                        <div className="relative mt-3 pt-3 border-t">
                          <input
                            id="welcome_image_replace"
                            name="welcome_image_replace"
                            type="file"
                            accept="image/*"
                            onChange={handleImageChange}
                            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
                          />
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            className="w-full relative z-0 hover:bg-primary/5 hover:border-primary/50 hover:text-primary transition-colors"
                          >
                            <svg
                              className="w-4 h-4 mr-2"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
                              />
                            </svg>
                            Replace Image
                          </Button>
                        </div>
                      </div>
                    </div>
                  )}
                  
                  {/* Loading state */}
                  {imageLoading && (
                    <div className="flex items-center justify-center gap-3 p-4 rounded-lg bg-primary/5 border border-primary/20">
                      <div className="animate-spin rounded-full h-5 w-5 border-2 border-primary border-t-transparent"></div>
                      <span className="text-sm font-medium text-primary">Uploading image...</span>
                    </div>
                  )}
                </div>
              </div>
              <div>
                <div className="mb-1">Welcome Title</div>
                <Input
                  id="welcome_title"
                  name="welcome_title"
                  value={formData.welcome_title}
                  onChange={handleInputChange}
                  placeholder="Enter welcome title"
                />
              </div>
              <div>
                <div className="mb-1">Welcome Message</div>
                <Textarea
                  id="welcome_message"
                  name="welcome_message"
                  value={formData.welcome_message}
                  onChange={handleInputChange}
                  placeholder="Enter welcome message"
                />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <div className="mb-1">Token Based Authentication</div>
                  <p className="text-sm text-muted-foreground">
                    Enable token based authentication for this agent
                  </p>
                </div>
                <Switch
                  checked={formData.token_based_auth ?? false}
                  onCheckedChange={handleSwitchChange}
                />
              </div>

              <div>
                <div className="mb-1">Frequently Asked Question</div>
                <div className="space-y-2">
                  {formData.possible_queries.map((query, index) => (
                    <div key={index} className="flex items-center gap-2">
                      <Input
                        value={query}
                        onChange={(e) =>
                          handlePossibleQueryChange(index, e.target.value)
                        }
                        placeholder="Enter a sample query"
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => removePossibleQuery(index)}
                        // disabled={formData.possible_queries.length <= 1}
                        className="px-2 h-9"
                      >
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    </div>
                  ))}
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={addPossibleQuery}
                    className="h-8 px-2 text-primary hover:text-primary"
                  >
                    <Plus className="h-4 w-4 mr-1" />
                    Add
                  </Button>
                </div>
                {formData.possible_queries.length > 0 && (
                  <div className="px-4 py-3 space-y-2 bg-white">
                    {formData.possible_queries.map((query, index) => (
                      <div key={index} className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground w-5 text-center">
                          {index + 1}.
                        </span>
                        <Input
                          value={query}
                          onChange={(e) =>
                            handlePossibleQueryChange(index, e.target.value)
                          }
                          placeholder="Enter a sample query"
                          className="flex-1"
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => removePossibleQuery(index)}
                          className="px-2 h-9 shrink-0"
                        >
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
                {formData.possible_queries.length === 0 && (
                  <div className="px-4 py-6 bg-white text-center">
                    <p className="text-sm text-muted-foreground">
                      No FAQs added yet. Add questions to help guide users.
                    </p>
                  </div>
                )}
              </div>

              <div className="border border-border rounded-lg overflow-hidden">
                <div className="flex items-center justify-between px-4 py-3 bg-muted/30">
                  <div className="flex items-center gap-2">
                    <MessageSquare className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium">
                      Thinking Phrases
                    </span>
                    {formData.thinking_phrases.length > 0 && (
                      <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
                        {formData.thinking_phrases.length}
                      </span>
                    )}
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={addThinkingPhrase}
                    className="h-8 px-2 text-primary hover:text-primary"
                  >
                    <Plus className="h-4 w-4 mr-1" />
                    Add
                  </Button>
                </div>
                {formData.thinking_phrases.length > 0 ? (
                  <div className="px-4 py-3 space-y-3 bg-white">
                    <p className="text-xs text-muted-foreground">
                      Separate multiple phrases with | (e.g., "Thinking...|Processing...")
                    </p>
                    {formData.thinking_phrases.map((phrase, index) => (
                      <div key={index} className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground w-5 text-center">
                          {index + 1}.
                        </span>
                        <Input
                          value={phrase}
                          onChange={(e) =>
                            handleThinkingPhraseChange(index, e.target.value)
                          }
                          placeholder="I think...|Getting the data..."
                          className="flex-1"
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => removeThinkingPhrase(index)}
                          className="px-2 h-9 shrink-0"
                        >
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </div>
                    ))}
                    <div className="pt-2 border-t border-border">
                      <div className="mb-1.5 text-sm text-muted-foreground">
                        Delay between phrases (seconds)
                      </div>
                      <Input
                        id="thinking_phrase_delay"
                        name="thinking_phrase_delay"
                        type="number"
                        min="0"
                        value={formData.thinking_phrase_delay}
                        onChange={handleInputChange}
                        placeholder="0"
                        className="max-w-[120px]"
                      />
                    </div>
                  </div>
                ) : (
                  <div className="px-4 py-6 bg-white text-center">
                    <p className="text-sm text-muted-foreground">
                      No thinking phrases added. These appear while the agent is processing.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Submit buttons */}
          {!hideButtons && (
            <div
              className={`flex justify-end gap-3 ${
                plain ? "pt-6 mt-2 border-t" : ""
              }`}
            >
              <Button type="button" variant="outline" onClick={() => onClose?.()}>
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
          )}
        </div>
      </form>
    </>
  );
};

export const AgentFormPage: React.FC = () => {
  const { agentId } = useParams<{ agentId: string }>();
  const id = agentId;
  const navigate = useNavigate();
  const isEditMode = !!id;
  const [formData, setFormData] = useState<AgentFormData>({
    id: isEditMode ? id : undefined,
    name: "",
    description: "",
    welcome_message: undefined,
    welcome_title: undefined,
    thinking_phrase_delay: undefined,
    possible_queries: [],
    thinking_phrases: [],
    token_based_auth: false,
  });
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<boolean>(false);

  React.useEffect(() => {
    if (isEditMode) {
      const fetchAgentConfig = async () => {
        try {
          setLoading(true);
          const config = await getAgentConfig(id);
          const cleanedQueries = config.possible_queries?.filter(
            (q) => q.trim() !== ""
          );
          const cleanedThinkingPhrases = Array.isArray(config.thinking_phrases)
            ? config.thinking_phrases.filter((p) => p.trim() !== "")
            : [];

          setFormData({
            ...config,
            possible_queries: cleanedQueries.length > 0 ? cleanedQueries : [],
            thinking_phrases:
              cleanedThinkingPhrases.length > 0 ? cleanedThinkingPhrases : [],
            token_based_auth: config.token_based_auth ?? false,
          });

          setError(null);
        } catch (err) {
          setError("Failed to load agent configuration");
        } finally {
          setLoading(false);
        }
      };

      fetchAgentConfig();
    }
  }, [id, isEditMode]);
  if (!agentId) {
    return (
      <div className="dashboard max-w-7xl mx-auto space-y-6 pt-8">
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
              {isEditMode ? "Edit Workflow" : "Create New Workflow"}
            </h2>
          </div>
          <AgentForm data={formData} />
        </div>
      </div>
    );
  }
};

interface AgentDialogProps {
  isOpen: boolean;
  onClose: () => void;
  data: AgentFormData | null;
  // disable redirect after create
  redirectOnCreate?: boolean;
  onCreated?: (agentId: string) => void;
}

export const AgentFormDialog = ({
  isOpen,
  onClose,
  data,
  redirectOnCreate,
  onCreated,
}: AgentDialogProps) => {
  const formId = "agent-form-dialog";
  const isEditMode = !!data?.id;

  return (
    <Sheet open={isOpen} onOpenChange={onClose}>
      <SheetContent className="sm:max-w-lg w-full flex flex-col p-0">
        <SheetHeader className="p-6 pb-4 border-b shrink-0">
          <SheetTitle className="text-xl font-semibold">
            {data?.id ? "Edit Agent" : "Create New Agent"}
          </SheetTitle>
          <SheetDescription>
            {data?.id
              ? "Update your agent's configuration and settings."
              : "Configure your new AI agent with a name, description, and welcome settings."}
          </SheetDescription>
        </SheetHeader>
        <div className="flex-1 overflow-y-auto overflow-x-hidden px-6 pt-4 pb-6">
          <AgentForm
            data={data || undefined}
            plain={true}
            onClose={onClose}
            redirectOnCreate={redirectOnCreate}
            onCreated={onCreated}
            hideButtons={true}
            formId={formId}
          />
        </div>
        {/* Sticky Footer with Action Buttons */}
        <div className="shrink-0 border-t bg-background px-6 py-4 flex justify-end gap-3">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form={formId}>
            {isEditMode ? "Update Agent" : "Create Agent"}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
};
export default AgentForm;
