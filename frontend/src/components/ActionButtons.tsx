import { Pencil, Trash2, Undo2 } from "lucide-react";
import { Button } from "@/components/button";

interface ActionButtonsProps {
  onEdit: () => void;
  onDelete: () => void;
  onRevert?: () => void;
  editTitle?: string;
  deleteTitle?: string;
  revertTitle?: string;
  canEdit?: boolean;
  canDelete?: boolean;
  canRevert?: boolean;
}

export function ActionButtons({
  onEdit,
  onDelete,
  onRevert,
  editTitle = "Edit",
  deleteTitle = "Delete",
  revertTitle = "Revert",
  canEdit = true,
  canDelete = true,
  canRevert = false,
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
      {canRevert && onRevert && (
        <Button variant="ghost" size="sm" onClick={onRevert} title={revertTitle}>
          <Undo2 className="w-4 h-4 text-emerald-600" />
        </Button>
      )}
    </div>
  );
}
