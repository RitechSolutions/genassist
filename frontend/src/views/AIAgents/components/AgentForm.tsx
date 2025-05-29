import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  createAgentConfig,
  getAgentConfig,
  updateAgentConfig,
} from "@/services/api";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { ChevronLeft, AlertCircle, CheckCircle2, Trash2 } from "lucide-react";
import { createWorkflow, updateWorkflow } from "@/services/workflows";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface AgentFormData {
  id?: string;
  name: string;
  description: string;
  welcome_message?: string;
  possible_queries?: string[];
  is_active?: boolean;
  workflow_id?: string;
}

interface AgentFormProps {
  data?: AgentFormData;
  plain?: boolean;
  onClose?: () => void;
}

const AgentForm: React.FC<AgentFormProps> = ({
  data,
  plain = false,
  onClose,
}: AgentFormProps) => {
  const id = data?.id;
  const navigate = useNavigate();
  const isEditMode = !!id;
  const cleanedQueries =
    data?.possible_queries?.filter((q) => q.trim() !== "") ?? [];

  const [formData, setFormData] = useState<AgentFormData>({
    ...(data || {
      name: "",
      description: "",
      welcome_message: "",
      possible_queries: [],
    }),
    possible_queries: cleanedQueries.length > 0 ? cleanedQueries : [],
  });

  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<boolean>(false);

  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      setLoading(true);

      if (isEditMode) {
        const { id: _, ...dataToSubmit } = formData;
        await updateAgentConfig(id, dataToSubmit);
        setSuccess(true);
        // if (data?.workflow_id) {

        //   await updateWorkflow(data?.workflow_id, {
        //     name: dataToSubmit.name,
        //     description: dataToSubmit.description,
        //     version: "1.0",
        //   });
        // }
        onClose?.();
        // navigate(`/ai-agents/workflow/${id}`);
      } else {
        const { id: _, ...dataToSubmit } = formData;

        const agentConfig = await createAgentConfig({
          ...dataToSubmit,
        });
        navigate(`/ai-agents/workflow/${agentConfig.id}`);
      }

      setError(null);
    } catch (err: unknown) {
      const errorMessage =
        err instanceof Error ? err.message : "Unknown error occurred";
      setError(
        `Failed to ${isEditMode ? "update" : "create"} agent. ${errorMessage}`
      );
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {error && (
        <div className="flex items-center gap-2 p-3 text-destructive bg-destructive/10 rounded-md">
          <AlertCircle className="h-4 w-4" />
          <p className="text-sm font-medium">
          {(error.includes("email") && error.includes("exist")) || error.includes("400")
             ? "This agent name already exists. Please use a different agent name."
             : error}
          </p>
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
          <div className={`${plain ? "" : "rounded-lg border bg-white p-6 "}`}>
            <div className="space-y-6">
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
    possible_queries: [],
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

          setFormData({
            ...config,
            possible_queries: cleanedQueries.length > 0 ? cleanedQueries : [],
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
              {isEditMode ? "Edit Agent" : "Create New Agent"}
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
}

export const AgentFormDialog = ({
  isOpen,
  onClose,
  data,
}: AgentDialogProps) => {
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="text-xl font-semibold">
            {data?.id ? "Edit Agent" : "Create New Agent"}
          </DialogTitle>
        </DialogHeader>
        <AgentForm data={data} plain={true} onClose={onClose} />
      </DialogContent>
    </Dialog>
  );
};
export default AgentForm;
