import React, { useId } from "react";
import { Label } from "@/components/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import type { LLMProvider } from "@/interfaces/llmProvider.interface";

interface ProviderSelectProps {
  /** Names the operation the model serves; two of these can be on screen at once */
  label: string;
  providers: readonly LLMProvider[];
  value: string;
  onChange: (id: string) => void;
  /** An empty list is a state to report, not a choice to prompt for */
  isEmpty: boolean;
}

/** One model picker. Mounted once per operation, so each keeps its own selection */
export const ProviderSelect: React.FC<ProviderSelectProps> = ({
  label,
  providers,
  value,
  onChange,
  isEmpty,
}) => {
  const triggerId = useId();

  return (
    <div className="space-y-2">
      <Label htmlFor={triggerId}>{label}</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger id={triggerId} className="w-full">
          <SelectValue
            placeholder={
              isEmpty
                ? "No active LLM providers are available"
                : "Select provider"
            }
          />
        </SelectTrigger>
        <SelectContent>
          {providers.map((provider) => (
            <SelectItem key={provider.id} value={provider.id}>
              {provider.name} ({provider.llm_model_provider} -{" "}
              {provider.llm_model})
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
};
