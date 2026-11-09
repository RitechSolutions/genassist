import React from "react";
import { Label } from "@/components/label";
import { DraggableInput } from "./custom/DraggableInput";

export interface SalesforceContactValues {
  web_email: string;
  web_name: string;
  web_phone: string;
}

interface SalesforceContactFieldsProps {
  values: SalesforceContactValues;
  onChange: (field: keyof SalesforceContactValues, value: string) => void;
}

const CONTACT_INPUTS: Array<{
  field: keyof SalesforceContactValues;
  label: string;
  placeholder: string;
}> = [
  { field: "web_email", label: "Web Email", placeholder: "e.g., alice@example.com" },
  { field: "web_name", label: "Web Name", placeholder: "e.g., Alice Smith" },
  { field: "web_phone", label: "Web Phone", placeholder: "e.g., +1 555 0100" },
];

export const SalesforceContactFields: React.FC<SalesforceContactFieldsProps> = ({ values, onChange }) => (
  <div className="space-y-2">
    <Label className="font-bold">Contact Details</Label>
    {CONTACT_INPUTS.map(({ field, label, placeholder }) => (
      <div key={field} className="space-y-2">
        <Label htmlFor={field}>{label}</Label>
        <DraggableInput
          id={field}
          value={values[field]}
          onChange={(e) => onChange(field, e.target.value)}
          placeholder={placeholder}
          className="w-full break-all"
        />
      </div>
    ))}
    <p className="text-xs text-muted-foreground">
      Optional. Fills the Case&apos;s Web Email, Web Name and Web Phone fields. A box here overrides a custom
      field with the same name.
    </p>
  </div>
);
