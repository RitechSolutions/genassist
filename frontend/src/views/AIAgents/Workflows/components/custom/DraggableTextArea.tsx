import React from "react";
import { Label } from "@/components/label";
import { cn } from "@/lib/utils";
import { Textarea } from "@/components/textarea";
import { useDraggableField } from "./useDraggableField";

interface DraggableTextAreaProps {
  id?: string;
  label?: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  placeholder?: string;
  className?: string;
  rows?: number;
  onVariableDrop?: (path: string, value: unknown) => void;
}

export const DraggableTextArea: React.FC<DraggableTextAreaProps> = ({
  id,
  label,
  value,
  onChange,
  placeholder,
  className,
  rows = 4,
  onVariableDrop,
}) => {
  const { isDragOver, ref, handleDragOver, handleDragLeave, handleDrop } =
    useDraggableField<HTMLTextAreaElement>(value, onChange, onVariableDrop);

  return (
    <div className="space-y-2 w-full">
      {label && <Label htmlFor={id}>{label}</Label>}
      <div className={cn("relative w-full", isDragOver && "ring-2 ring-blue-500 ring-opacity-50")}>
        <Textarea
          ref={ref}
          id={id}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          rows={rows}
          className={cn("w-full transition-colors", isDragOver && "border-blue-500 bg-blue-50", className)}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        />
        {isDragOver && (
          <div className="absolute inset-0 flex items-center justify-center bg-blue-100 bg-opacity-50 rounded-md pointer-events-none z-10">
            <span className="text-blue-600 font-medium text-sm bg-white px-3 py-1 rounded-full shadow-sm">
              Drop variable here
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
