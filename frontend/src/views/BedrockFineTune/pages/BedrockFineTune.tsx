import { useState } from "react";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { BedrockFineTuneJobsCard } from "@/views/BedrockFineTune/components/BedrockFineTuneJobsCard";
import { BedrockFineTuneJobDialog } from "@/views/BedrockFineTune/components/BedrockFineTuneJobDialog";
import { GenerateFromConversationsDialog } from "@/views/BedrockFineTune/components/GenerateFromConversationsDialog";
import { SelectExistingBedrockFileDialog } from "@/views/BedrockFineTune/components/SelectExistingBedrockFileDialog";
import type { S3FileRef } from "@/views/BedrockFineTune/types";

export default function BedrockFineTune() {
  const [searchQuery, setSearchQuery] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  const [trainingData, setTrainingData] = useState<S3FileRef | null>(null);
  const [validationData, setValidationData] = useState<S3FileRef | null>(null);
  const [generateTarget, setGenerateTarget] = useState<"training" | "validation" | null>(null);
  const [selectFileTarget, setSelectFileTarget] = useState<"training" | "validation" | null>(null);

  const handleSetData = (target: "training" | "validation", data: S3FileRef | null) => {
    if (target === "training") setTrainingData(data);
    else setValidationData(data);
  };

  const handleJobCreated = () => {
    setRefreshKey((k) => k + 1);
  };

  return (
    <PageLayout>
      <PageHeader
        title="Bedrock Fine-Tune"
        subtitle="Create and manage Amazon Nova fine-tuning jobs"
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search jobs..."
        actionButtonText="New Fine-Tune Job"
        onActionClick={() => setIsDialogOpen(true)}
      />

      <BedrockFineTuneJobsCard
        searchQuery={searchQuery}
        refreshKey={refreshKey}
        onNewFineTuneJob={() => setIsDialogOpen(true)}
      />

      <BedrockFineTuneJobDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onJobCreated={handleJobCreated}
        trainingData={trainingData}
        validationData={validationData}
        onSetData={handleSetData}
        onOpenGenerate={setGenerateTarget}
        onOpenSelectFile={setSelectFileTarget}
      />

      {generateTarget && (
        <GenerateFromConversationsDialog
          isOpen={!!generateTarget}
          onOpenChange={(open) => { if (!open) setGenerateTarget(null); }}
          fileType={generateTarget}
          onFileGenerated={(data) => {
            handleSetData(generateTarget, data);
            setGenerateTarget(null);
          }}
        />
      )}

      {selectFileTarget && (
        <SelectExistingBedrockFileDialog
          isOpen={!!selectFileTarget}
          onOpenChange={(open) => { if (!open) setSelectFileTarget(null); }}
          fileType={selectFileTarget}
          onFileSelected={(data) => {
            handleSetData(selectFileTarget, data);
            setSelectFileTarget(null);
          }}
        />
      )}
    </PageLayout>
  );
}
