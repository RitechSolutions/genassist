import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Loader2 } from "lucide-react";
import { toast } from "react-hot-toast";
import { listOpenAIFiles } from "@/services/openaiFineTune";
import type { OpenAIFileItem } from "@/interfaces/fineTune.interface";

interface Props {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  fileType: "training" | "validation";
  onFileSelected: (file: { id: string; name: string }) => void;
}

export function SelectExistingFileDialog({ isOpen, onOpenChange, fileType, onFileSelected }: Props) {
  const [files, setFiles] = useState<OpenAIFileItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!isOpen) return;
    setSearch("");
    setIsLoading(true);
    listOpenAIFiles()
      .then((result) => setFiles(result.filter((f) => f.purpose === "fine-tune")))
      .catch(() => toast.error("Failed to load files"))
      .finally(() => setIsLoading(false));
  }, [isOpen]);

  const filtered = search
    ? files.filter((f) => (f.filename ?? "").toLowerCase().includes(search.toLowerCase()))
    : files;

  const handleSelect = (file: OpenAIFileItem) => {
    onFileSelected({ id: file.id, name: file.filename ?? file.id });
    onOpenChange(false);
  };

  const fileTypeLabel = fileType === "training" ? "Training" : "Validation";

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[620px] p-0 overflow-hidden">
        <DialogHeader className="px-6 pt-6 pb-2">
          <DialogTitle>Select {fileTypeLabel} File</DialogTitle>
        </DialogHeader>

        <div className="px-6 pb-3">
          <Label className="text-xs mb-1 block">Search by filename</Label>
          <Input
            placeholder="e.g. training_data"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <div className="max-h-[50vh] overflow-y-auto px-6">
          {isLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
              <Loader2 className="w-4 h-4 animate-spin" /> Loading files…
            </div>
          ) : filtered.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4">No uploaded files found.</p>
          ) : (
            <div className="space-y-2 py-2">
              {filtered.map((file) => (
                <div
                  key={file.id}
                  className="flex items-center justify-between border rounded px-3 py-2.5 gap-3"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">{file.filename ?? file.id}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {file.bytes ? `${(file.bytes / 1024).toFixed(1)} KB · ` : ""}
                      {file.id}
                    </p>
                  </div>
                  <Button size="sm" variant="outline" onClick={() => handleSelect(file)}>
                    Select
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>

        <DialogFooter className="border-t px-6 py-3">
          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}