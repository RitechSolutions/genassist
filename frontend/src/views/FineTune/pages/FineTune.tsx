import { useState } from "react";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { FineTuneJobsCard } from "@/views/FineTune/components/FineTuneJobsCard";
import { FineTuneJobDialog } from "@/views/FineTune/components/FineTuneJobDialog";
import { GenerateFromConversationsDialog } from "@/views/FineTune/components/GenerateFromConversationsDialog";
import { SelectExistingFileDialog } from "@/views/FineTune/components/SelectExistingFileDialog";

export default function FineTune() {
  const [searchQuery, setSearchQuery] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  const [trainingFile, setTrainingFile] = useState<{ id: string; name: string } | null>(null);
  const [validationFile, setValidationFile] = useState<{ id: string; name: string } | null>(null);
  const [generateTarget, setGenerateTarget] = useState<"training" | "validation" | null>(null);
  const [selectFileTarget, setSelectFileTarget] = useState<"training" | "validation" | null>(null);

  const handleSetFile = (target: "training" | "validation", file: { id: string; name: string } | null) => {
    if (target === "training") setTrainingFile(file);
    else setValidationFile(file);
  };

  const handleJobCreated = () => {
    setRefreshKey((k) => k + 1);
  };

  return (
    <PageLayout>
      <PageHeader
        title="Fine-Tune"
        subtitle="Create and manage fine-tuning jobs"
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search jobs..."
        actionButtonText="New Fine-Tune Job"
        onActionClick={() => setIsDialogOpen(true)}
      />

      <FineTuneJobsCard searchQuery={searchQuery} refreshKey={refreshKey} />

      <FineTuneJobDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onJobCreated={handleJobCreated}
        trainingFile={trainingFile}
        validationFile={validationFile}
        onSetFile={handleSetFile}
        onOpenGenerate={setGenerateTarget}
        onOpenSelectFile={setSelectFileTarget}
      />

      {generateTarget && (
        <GenerateFromConversationsDialog
          isOpen={!!generateTarget}
          onOpenChange={(open) => { if (!open) setGenerateTarget(null); }}
          fileType={generateTarget}
          onFileGenerated={(file) => {
            handleSetFile(generateTarget, file);
            setGenerateTarget(null);
          }}
        />
      )}

      {selectFileTarget && (
        <SelectExistingFileDialog
          isOpen={!!selectFileTarget}
          onOpenChange={(open) => { if (!open) setSelectFileTarget(null); }}
          fileType={selectFileTarget}
          onFileSelected={(file) => {
            handleSetFile(selectFileTarget, file);
            setSelectFileTarget(null);
          }}
        />
      )}
    </PageLayout>
  );
}