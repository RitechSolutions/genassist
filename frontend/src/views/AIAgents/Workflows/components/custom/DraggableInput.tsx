import React from "react";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { cn } from "@/lib/utils";
import { useDraggableField } from "./useDraggableField";

interface DraggableInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  id?: string;
  label?: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  placeholder?: string;
  className?: string;
  onVariableDrop?: (path: string, value: unknown) => void;
}

export const DraggableInput: React.FC<DraggableInputProps> = ({
  id,
  label,
  value,
  onChange,
  placeholder,
  className,
  onVariableDrop,
  ...props
}) => {
  const { isDragOver, ref, handleDragOver, handleDragLeave, handleDrop } =
    useDraggableField<HTMLInputElement>(value, onChange, onVariableDrop);

  return (
    <div className="space-y-2 w-full">
      {label && <Label htmlFor={id}>{label}</Label>}
      <div className={cn("relative w-full", isDragOver && "ring-2 ring-blue-500 ring-opacity-50")}>
        <Input
          ref={ref}
          id={id}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          className={cn("w-full transition-colors", isDragOver && "border-blue-500 bg-blue-50", className)}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          {...props}
        />
        {isDragOver && (
          <div className="absolute inset-0 flex items-center justify-center bg-blue-100 bg-opacity-50 rounded-md pointer-events-none z-10">
            <span className="text-blue-600 font-medium text-sm bg-white px-3 py-1 rounded-full shadow-sm">
              Drop variable at cursor position
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
