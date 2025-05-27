import React, { ReactNode } from "react";
import { Label } from "@/components/label";

interface FormFieldProps {
  id?: string;
  label: string;
  children: ReactNode;
  className?: string;
  error?: string;
}

export function FormField({ id, label, children, className = "", error }: FormFieldProps) {
  return (
    <div className={className}>
      <Label htmlFor={id} className="text-sm font-medium">
        {label}
      </Label>
      <div className="mt-1.5">
        {children}
      </div>
      {error && (
        <p className="text-sm text-red-500 mt-1">{error}</p>
      )}
    </div>
  );
} 