import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getToolById, updateTool } from "@/services/tools";
import { ToolSection } from "./ToolSection";
import { ToolParameter } from "@/interfaces/tool.interface";
import { Input } from "@/components/input";
import { Textarea } from "@/components/textarea";
import { Button } from "@/components/button";
import toast from "react-hot-toast";
import { v4 as uuidv4 } from "uuid";

export default function EditTool() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [parameters, setParameters] = useState<ToolParameter[]>([]);
  const [tab, setTab] = useState("form");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!id) return;
    async function fetchTool() {
      try {
        const tool = await getToolById(id); 
        setName(tool.name || "");
        setDescription(tool.description || "");
        setParameters(tool.parameters || []);
      } catch (error) {
        console.error("Failed to fetch tool", error);
      } finally {
        setLoading(false);
      }
    }
    fetchTool();
  }, [id]);

  const handleSubmit = async () => {
    if (!name.trim()) {
      toast.error("Name is required");
      return;
    }
    setSubmitting(true);
    try {
      await updateTool(id, {
        name,
        description,
        parameters,
      });
      navigate("/tools");
    } catch (error) {
      console.error("Failed to update tool", error);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Edit Tool</h1>
      <div className="space-y-4">
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Tool Name"
        />
        <Textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Tool Description"
        />

        <ToolSection
          title="Tool Parameters"
          subtitle="Define parameters for your tool."
          items={parameters}
          setItems={setParameters}
          tab={tab}
          setTab={setTab}
          addItem={(setter, sample) => {
            setter(prev => [...prev, { id: uuidv4(), ...sample }]);
          }}
          removeItem={(setter, id) => {
            setter(prev => prev.filter((item) => item.id !== id));
          }}
          sample={{ name: "", value: "" }}
        />

        <div className="flex justify-end gap-2">
          <Button onClick={() => navigate("/tools")}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={submitting}>
            {submitting ? "Updating..." : "Update Tool"}
          </Button>
        </div>
      </div>
    </div>
  );
}
