import { FC } from "react";
import { Input } from "@/components/input";
import { Textarea } from "@/components/textarea";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/select";

interface BasicInfoProps {
  name: string;
  onNameChange: (v: string) => void;
  description: string;
  onDescriptionChange: (v: string) => void;
  toolType: "api" | "function";
  onToolTypeChange: (v: "api" | "function") => void;
}

export const BasicInfo: FC<BasicInfoProps> = ({
  name,
  onNameChange,
  description,
  onDescriptionChange,
  toolType,
  onToolTypeChange,
}) => (
  <div className="grid md:grid-cols-3 gap-6">
    <div className="hidden md:block">
      <h2 className="text-lg font-medium">Basic Information</h2>
      <p className="text-sm text-muted-foreground mt-1">
        Basic information about the tool
      </p>
    </div>
    <div className="col-span-2 space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium">Name</label>
          <Input
            className="w-full"
            placeholder="Name for this tool"
            value={name}
            onChange={e => onNameChange(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium">Type</label>
          <Select value={toolType} onValueChange={onToolTypeChange}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="api">API</SelectItem>
              <SelectItem value="function">Python Function</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="flex flex-col gap-2">
        <label className="text-sm font-medium">Description</label>
        <Textarea
          className="w-full"
          placeholder="Brief description of this tool"
          value={description}
          onChange={e => onDescriptionChange(e.target.value)}
        />
      </div>
    </div>
  </div>
);
