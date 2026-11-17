import React from "react";
import { Label } from "@/components/label";
import { RichInput } from "@/components/richInput";

interface FirstToolFieldProps {
  id: string;
  value: string;
  onChange: (value: string) => void;
}

/** The tool a ReActAgentLC agent calls before answering each message. */
export const FirstToolField: React.FC<FirstToolFieldProps> = ({ id, value, onChange }) => (
  <div className="space-y-2">
    <Label htmlFor={`first-tool-input-${id}`}>Always call this tool first</Label>
    <RichInput
      id={`first-tool-input-${id}`}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder="Tool name or {{variable}}"
      className="w-full"
    />
    <p className="text-xs text-muted-foreground">
      The agent calls this connected tool before answering each message, for example a
      knowledge base search. Leave empty to let the agent decide.
    </p>
  </div>
);
