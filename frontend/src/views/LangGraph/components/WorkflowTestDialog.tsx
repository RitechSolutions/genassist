import React, { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Loader2, Send } from "lucide-react";
import { testWorkflow, WorkflowTestResponse } from "@/services/workflows";
import { Workflow } from "@/interfaces/workflow.interface";
import { isArray } from "util";

interface WorkflowTestDialogProps {
  isOpen: boolean;
  onClose: () => void;
  workflowName: string;
  workflow: Workflow | null;
}

const WorkflowTestDialog: React.FC<WorkflowTestDialogProps> = ({
  isOpen,
  onClose,
  workflowName,
  workflow,
}) => {
  const [testMessage, setTestMessage] = useState("");
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<WorkflowTestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isDebugMode, setIsDebugMode] = useState(false);

  // Handle test workflow
  const handleTestWorkflow = async () => {
    if (!testMessage.trim() || !workflow) {
      return;
    }

    setTesting(true);
    setError(null);
    setResult(null);

    try {
      const response = await testWorkflow({
        message: testMessage,
        session: { thread_id: "test", user_id: "test_user_id", user_name: "test_user_name", base_url: "api.restful-api.dev" },
        workflow: workflow,
      });

      setResult(response);
    } catch (err) {
      console.error("Error testing workflow:", err);
      setError("Failed to test workflow. Please try again.");
    } finally {
      setTesting(false);
    }
  };

  // Get message role icon and color
  const getMessageStyle = (role: string) => {
    switch (role) {
      case "user":
        return {
          bgColor: "bg-blue-50",
          textColor: "text-blue-800",
          borderColor: "border-blue-100",
        };
      case "assistant":
        return {
          bgColor: "bg-green-50",
          textColor: "text-green-800",
          borderColor: "border-green-100",
        };
      case "system":
        return {
          bgColor: "bg-gray-50",
          textColor: "text-gray-800",
          borderColor: "border-gray-100",
        };
      default:
        return {
          bgColor: "bg-gray-50",
          textColor: "text-gray-800",
          borderColor: "border-gray-100",
        };
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Test Workflow: {workflowName}</DialogTitle>
          <DialogDescription>
            Test your workflow configuration with a sample message
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="test-message">Test Message</Label>
            <div className="flex gap-2">
              <Input
                id="test-message"
                placeholder="Enter a test message"
                value={testMessage}
                onChange={(e) => setTestMessage(e.target.value)}
                disabled={testing}
                className="flex-1"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleTestWorkflow();
                  }
                }}
              />
              <Button
                onClick={handleTestWorkflow}
                disabled={testing || !testMessage.trim() || !workflow}
                className="flex items-center gap-2"
              >
                {testing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
                Test
              </Button>
              <Button
                onClick={() => setIsDebugMode(!isDebugMode)}
                className="flex items-center gap-2"
                style={{ backgroundColor: isDebugMode ? "#000" : "#fff", color: isDebugMode ? "#fff" : "#000" }}
              >
                {"Debug"}
              </Button>
            </div>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-600 p-3 rounded-md">
              {error}
            </div>
          )}

          {result && (
            <div className="space-y-2">
              <Label>Result {result.status === "success" ? "✅" : "❌"}</Label>

              {result.status === "success" && (
                <div className="border rounded-md overflow-hidden">
                  <div className="max-h-80 overflow-y-auto p-2 space-y-3">
                    {/* Add the user's test message first */}
                    <div
                      className={`p-3 rounded-md border ${
                        getMessageStyle("user").bgColor
                      } ${getMessageStyle("user").borderColor}`}
                    >
                      <div className="font-semibold mb-1 text-xs uppercase text-blue-600">
                        You
                      </div>
                      <div className="whitespace-pre-wrap">{result.input}</div>
                    </div>

                    {/* Show each message in the result */}
                    {!isDebugMode ? (
                      <div
                        className={`p-3 rounded-md border bg-gray-50 border-gray-100`}
                      >
                        <div
                          className={`font-semibold mb-1 text-xs uppercase text-green-600`}
                        >
                          Response
                        </div>
                        <div className="whitespace-pre-wrap">
                          {result.output}
                        </div>
                      </div>
                    ) : (
                      <div
                        className={`p-3 rounded-md border bg-gray-50 border-gray-100`}
                      >
                        <div
                          className={`font-semibold mb-1 text-xs uppercase text-green-600`}
                        >
                          Debug View
                        </div>
                        <div className="whitespace-pre-wrap">
                          {JSON.stringify(result, null, 2)}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {result.status !== "success" && (
                <div className="border border-red-200 rounded-md p-3 bg-red-50 text-sm text-red-600">
                  Error processing workflow
                </div>
              )}

              {result.workflow_id && (
                <div className="mt-2 text-xs text-gray-500">
                  Workflow ID: {result.workflow_id}
                </div>
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default WorkflowTestDialog;
