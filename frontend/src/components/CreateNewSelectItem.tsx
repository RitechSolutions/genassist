import React from "react";
import { SelectItem } from "@/components/select";
import { Plus } from "lucide-react";

interface CreateNewSelectItemProps {
  label?: string;
}

export const CreateNewSelectItem: React.FC<CreateNewSelectItemProps> = ({
  label = "Create new",
}) => {
  return (
    <SelectItem value="__create__">
      <div className="flex items-center gap-2">
        <Plus className="w-4 h-4" /> {label}
      </div>
    </SelectItem>
  );
};

