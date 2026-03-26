import { Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/button";

interface ActionButtonsProps {
  onEdit: () => void;
  onDelete: () => void;
  editTitle?: string;
  deleteTitle?: string;
  canEdit?: boolean;
  canDelete?: boolean;
}

export function ActionButtons({
  onEdit,
  onDelete,
  editTitle = "Edit",
  deleteTitle = "Delete",
  canEdit = true,
  canDelete = true,
}: ActionButtonsProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {canEdit && (
        <Button variant="ghost" size="sm" onClick={onEdit} title={editTitle}>
          <Pencil className="w-4 h-4 text-black" />
        </Button>
      )}
      {canDelete && (
        <Button variant="ghost" size="sm" onClick={onDelete} title={deleteTitle}>
          <Trash2 className="w-4 h-4 text-red-500" />
        </Button>
      )}
    </div>
  );
}
