import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Button } from "@/components/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { toast } from "react-hot-toast";
import { uploadAudio } from "@/services/audioUpload";
import { AudioLines, X } from "lucide-react";
import { useAgents } from "../hooks/useAgents";

interface UploadMediaDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
}

export function UploadMediaDialog({
  isOpen,
  onOpenChange,
}: UploadMediaDialogProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { agents, imageErrors, setImageErrors } = useAgents();
  const navigate = useNavigate();

  const checkAuthentication = (): boolean => {
    const token = localStorage.getItem('access_token');
    const isAuthenticated = localStorage.getItem('isAuthenticated') === 'true';
    
    if (!token || !isAuthenticated) {
      return false;
    }
    
    return true;
  };

  const getInitials = (firstName = "", lastName = "") => {
    return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
  };

  const handleFileDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const files = event.dataTransfer.files;
    if (files.length > 0) {
      setSelectedFile(files[0]);
      toast.success(`File selected: ${files[0].name}`);
    }
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files?.length) {
      setSelectedFile(event.target.files[0]);
    }
  };

  const handleRemoveFile = () => {
    setSelectedFile(null);
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      toast.error("Please select a file to upload.");
      return;
    }
  
    if (!selectedAgent) {
      toast.error("Please select an operator.");
      return;
    }

    if (!checkAuthentication()) {
      toast.error("You need to be logged in to upload files.");
      navigate("/login");
      return;
    }
  
    const processingToast = toast.loading("Processing audio file...");
    setLoading(true);
  
    try {
      const response = await uploadAudio(selectedFile, selectedAgent);
  
      toast.dismiss(processingToast);
      
      if (response.success) {
        toast.success("Audio processed successfully!");
        onOpenChange(false);
        setSelectedFile(null);
        setSelectedAgent(null);
      } else {
        toast.error(response.message || "An error occurred during processing");
      }
  
    } catch (error) {
      toast.dismiss(processingToast);
      console.error("Upload error:", error);
      
      const errorMsg = error instanceof Error ? error.message : "Upload failed. Please try again.";
      if (errorMsg.includes("401") || errorMsg.includes("Unauthorized") || errorMsg.includes("Not authenticated")) {
        toast.error("Your session has expired. Please log in again.");
        localStorage.removeItem("isAuthenticated");
        navigate("/login");
      } else {
        toast.error(errorMsg);
      }
    } finally {
      setLoading(false);
    }
  };
  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3">
            <AudioLines className="w-6 h-6 text-primary" />
            Upload Audio File
          </DialogTitle>
        </DialogHeader>

        <div
          className="border-dashed border-2 border-gray-300 p-14 text-center rounded-lg cursor-pointer hover:bg-gray-100 transition"
          onDrop={handleFileDrop}
          onChange={handleFileSelect}
          onDragOver={(event) => event.preventDefault()}
        >
          <input
            id="file-input"
            type="file"
            accept="audio/*"
            className="hidden"
            onChange={handleFileSelect}
          />
          {selectedFile ? (
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                {selectedFile.name}
              </p>
              <button onClick={handleRemoveFile} type="button">
                <X className="w-4 h-4 text-red-500" />
              </button>
            </div>
          ) : (
            <p
              className="text-sm text-gray-600"
              onClick={() => document.getElementById("file-input")?.click()}
            >
              Drag & Drop an audio file here or{" "}
              <span className="text-primary underline">click to select</span>
            </p>
          )}
        </div>

        <div className="mt-4">
          <label className="text-sm font-medium text-muted-foreground">
            Select Operator
          </label>
          <Select
            value={selectedAgent ?? ""}
            onValueChange={(value) => setSelectedAgent(value)}
          >
            <SelectTrigger className="mt-1">
              <SelectValue placeholder="Search & Select an Operator" />
            </SelectTrigger>
            <SelectContent>
              {agents.map((agent) => (
                <SelectItem
                  key={agent.id}
                  value={agent.id}
                  className="flex items-center gap-3"
                >
                  <div className="flex items-center gap-2">
                  {!imageErrors.has(agent.id) && agent.avatar ? (
                    <img
                      src={agent.avatar}
                      alt={`${agent.firstName} ${agent.lastName}`}
                      className="w-6 h-6 rounded-full object-cover border border-gray-300"
                      onError={() =>
                        setImageErrors((prev) => new Set(prev).add(agent.id))
                      }
                    />
                  ) : (
                    <div className="w-6 h-6 flex items-center justify-center rounded-full bg-gray-300 text-gray-700 font-bold">
                      {getInitials(agent.firstName, agent.lastName)}
                    </div>
                  )}
                  <span className="text-sm text-gray-800">
                    {agent.firstName} {agent.lastName}
                  </span>
                </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <Button
          className="w-full mt-4 h-12"
          onClick={handleUpload}
          disabled={loading}
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Processing...
            </span>
          ) : "Upload"}
        </Button>
      </DialogContent>
    </Dialog>
  );
} 