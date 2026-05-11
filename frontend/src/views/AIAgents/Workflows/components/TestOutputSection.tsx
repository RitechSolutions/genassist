import { Label } from "@/components/label";
import { Volume2 } from "lucide-react";
import JsonViewer from "@/components/JsonViewer";
import { getAudioUrl } from "../hooks/useAudioTest";

interface TestOutputSectionProps {
  output: string | Record<string, unknown> | null;
  error: string | null;
  isLoading: boolean;
}

export const TestOutputSection: React.FC<TestOutputSectionProps> = ({
  output,
  error,
  isLoading,
}) => (
  <div className="space-y-2">
    <div className="flex justify-between items-center">
      <Label>Output</Label>
      {isLoading && (
        <div className="text-xs text-blue-500">Loading...</div>
      )}
    </div>

    {error && (
      <div className="bg-red-50 border border-red-200 text-red-600 p-2 rounded-md text-xs mb-2">
        {error}
      </div>
    )}
    {output === null ? (
      <div className="whitespace-pre-wrap">No output yet</div>
    ) : typeof output === "string" ? (
      <div className="whitespace-pre-wrap">{output}</div>
    ) : (() => {
      const audioUrl = getAudioUrl(output);
      if (audioUrl) {
        return (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm text-teal-700 bg-teal-50 border border-teal-200 rounded-md px-3 py-2">
              <Volume2 className="h-4 w-4" />
              Audio generated successfully
            </div>
            <audio controls className="w-full" src={audioUrl} />
          </div>
        );
      }
      return (
        <JsonViewer
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          data={output as any}
          onCopy={(data) => {
            navigator.clipboard.writeText(
              JSON.stringify(data, null, 2)
            );
          }}
        />
      );
    })()}
  </div>
);
