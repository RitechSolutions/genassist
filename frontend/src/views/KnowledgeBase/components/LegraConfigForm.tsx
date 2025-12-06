import React from "react";
import { Textarea } from "@/components/textarea";
import { Switch } from "@/components/switch";
import { HelpCircle } from "lucide-react";

export interface Legra {
  enabled: boolean;
  questions: string;
  [key: string]: unknown;
}
interface LegraConfigFormProps {
  legraConfig: Legra;
  onChange: (updatedConfig: Legra) => void;
}

const LegraConfigForm: React.FC<LegraConfigFormProps> = ({
  legraConfig,
  onChange,
}) => {
  const handleLegraChange = (name: string, value: unknown) => {
    onChange({
      ...legraConfig,
      [name]: value,
    });
  };

  return (
    <div className="bg-gray-50 rounded-lg">
      <div className="flex items-center justify-between p-4">
        <div className="flex items-center gap-2">
          <HelpCircle className="h-5 w-5 text-gray-500" />
          <div>
            <div className="font-medium">Legra</div>
            <p className="text-sm text-gray-500">
              Enable Legra for graph building with custom questions
            </p>
          </div>
        </div>
        <Switch
          checked={legraConfig.enabled || false}
          onCheckedChange={(checked) => handleLegraChange("enabled", checked)}
        />
      </div>

      {legraConfig.enabled && (
        <div className="p-4 pt-0 space-y-2">
          <div>
            <div className="mb-1">Questions for Graph Building</div>
            <Textarea
              placeholder="Enter questions (one per line) that will be used by Legra during graph building..."
              value={legraConfig.questions || ""}
              onChange={(e) => handleLegraChange("questions", e.target.value)}
              rows={6}
              className="min-h-32"
            />
          </div>

          <p className="text-sm text-gray-500 mt-4">
            Add one question per line. These questions will guide Legra during
            the graph building process.
          </p>
        </div>
      )}
    </div>
  );
};

export default LegraConfigForm;
