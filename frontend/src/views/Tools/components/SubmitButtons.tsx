import { FC } from "react";
import { Button } from "@/components/button";

interface SubmitButtonsProps {
  onCancel: () => void;
  onSubmit: () => void;
  submitting: boolean;
  isEditMode: boolean;
}

export const SubmitButtons: FC<SubmitButtonsProps> = ({
  onCancel,
  onSubmit,
  submitting,
  isEditMode,
}) => (
  <div className="flex justify-end">
    <Button
      variant="outline"
      className="h-10 rounded-[8px] mr-2"
      onClick={onCancel}
    >
      Cancel
    </Button>
    <Button
      className="h-10 rounded-[8px]"
      onClick={onSubmit}
      disabled={submitting}
    >
      {submitting
        ? isEditMode
          ? "Updating..."
          : "Creating..."
        : isEditMode
        ? "Update Tool"
        : "Create Tool"}
    </Button>
  </div>
);
