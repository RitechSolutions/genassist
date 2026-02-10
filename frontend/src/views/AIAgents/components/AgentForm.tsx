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
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
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
}

interface AgentFormProps {
  data?: AgentFormData;
  plain?: boolean;
  onClose?: () => void;
  // When true, navigate to workflow after creating an agent
  redirectOnCreate?: boolean;
  onCreated?: (agentId: string) => void;
}

const AgentForm: React.FC<AgentFormProps> = ({
  data,
  plain = false,
  onClose,
  redirectOnCreate = true,
  onCreated,
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
    }),
    possible_queries: cleanedQueries.length > 0 ? cleanedQueries : [],
    thinking_phrases:
      cleanedThinkingPhrases.length > 0 ? cleanedThinkingPhrases : [],
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

      <form onSubmit={handleSubmit}>
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
                <div className="mb-1">Welcome Image</div>
                <div className="space-y-2">
                  {!imagePreview ? (
                    <div className="relative">
                      <Input
                        id="welcome_image"
                        name="welcome_image"
                        type="file"
                        accept="image/*"
                        onChange={handleImageChange}
                        className="sr-only"
                      />
                      <label
                        htmlFor="welcome_image"
                        className={`flex flex-col items-center justify-center w-full h-32 border-2 border-dashed rounded-lg transition-all cursor-pointer ${
                          isDragOver
                            ? "border-primary bg-primary/5 scale-105"
                            : "border-gray-300 hover:border-gray-400 bg-gray-50 hover:bg-gray-100"
                        }`}
                        onDragOver={handleDragOver}
                        onDragLeave={handleDragLeave}
                        onDrop={handleDrop}
                      >
                        <div className="flex flex-col items-center justify-center text-gray-500">
                          <div
                            className={`w-12 h-12 rounded-full flex items-center justify-center mb-2 transition-colors ${
                              isDragOver ? "bg-primary/20" : "bg-primary/10"
                            }`}
                          >
                            <svg
                              className={`w-6 h-6 transition-colors ${
                                isDragOver ? "text-primary" : "text-primary"
                              }`}
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                              />
                            </svg>
                          </div>
                          <p
                            className={`text-sm font-medium transition-colors ${
                              isDragOver ? "text-primary" : "text-gray-500"
                            }`}
                          >
                            {isDragOver ? "Drop image here" : "Upload Image"}
                          </p>
                          <p className="text-xs text-gray-400">
                            Click to select or drag and drop
                          </p>
                          <p className="text-xs text-gray-400">
                            PNG, JPG, GIF up to 5MB
                          </p>
                        </div>
                      </label>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <div className="relative inline-block">
                        <img
                          src={imagePreview}
                          alt="Preview"
                          className="h-32 w-32 object-cover rounded-lg border shadow-sm"
                        />
                        <Button
                          type="button"
                          variant="destructive"
                          size="sm"
                          onClick={handleRemoveImage}
                          disabled={imageDeleting}
                          className="absolute -top-2 -right-2 h-6 w-6 rounded-full p-0 shadow-md"
                        >
                          {imageDeleting ? "..." : "×"}
                        </Button>
                      </div>
                      {imageFile && (
                        <div className="text-xs text-muted-foreground">
                          {imageFile.name} (
                          {(imageFile.size / 1024 / 1024).toFixed(2)} MB)
                        </div>
                      )}
                      <div className="relative">
                        <Input
                          id="welcome_image_replace"
                          name="welcome_image_replace"
                          type="file"
                          accept="image/*"
                          onChange={handleImageChange}
                          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                        />
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          className="w-full"
                        >
                          Replace Image
                        </Button>
                      </div>
                    </div>
                  )}
                  {imageLoading && (
                    <div className="flex items-center justify-center text-sm text-muted-foreground">
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary mr-2"></div>
                      Uploading image...
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
                    onClick={addPossibleQuery}
                    className="w-full"
                  >
                    Add FAQ
                  </Button>
                </div>
              </div>

              <div>
                <div className="mb-1">
                  Thinking Phrases Set (separate with |)
                </div>
                <div className="space-y-2">
                  {formData.thinking_phrases.map((phrase, index) => (
                    <div key={index} className="flex items-center gap-2">
                      <Input
                        value={phrase}
                        onChange={(e) =>
                          handleThinkingPhraseChange(index, e.target.value)
                        }
                        placeholder="I think...|Getting the data..."
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => removeThinkingPhrase(index)}
                        // disabled={formData.thinking_phrases.length <= 1}
                        className="px-2 h-9"
                      >
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    </div>
                  ))}
                  {formData.thinking_phrases.length > 0 && (
                    <div>
                      <div className="mb-1">
                        Thinking Phrase Delay (seconds)
                      </div>
                      <Input
                        id="thinking_phrase_delay"
                        name="thinking_phrase_delay"
                        type="number"
                        min="0"
                        value={formData.thinking_phrase_delay}
                        onChange={handleInputChange}
                        placeholder="Enter delay in seconds"
                      />
                    </div>
                  )}
                  <Button
                    type="button"
                    onClick={addThinkingPhrase}
                    className="w-full"
                  >
                    Add Thinking Phrase
                  </Button>
                </div>
              </div>
            </div>
          </div>

          {/* Submit buttons */}
          <div className="flex justify-end gap-3">
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
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="text-xl font-semibold">
            {data?.id ? "Edit Agent" : "Create New Agent"}
          </DialogTitle>
        </DialogHeader>
        <AgentForm
          data={data || undefined}
          plain={true}
          onClose={onClose}
          redirectOnCreate={redirectOnCreate}
          onCreated={onCreated}
        />
      </DialogContent>
    </Dialog>
  );
};
export default AgentForm;
