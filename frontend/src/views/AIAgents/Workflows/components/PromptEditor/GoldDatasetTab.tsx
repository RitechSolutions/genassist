import React, { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Database, Plus, Trash2, Edit2, Check, X } from "lucide-react";
import { Button } from "@/components/button";
import { Textarea } from "@/components/textarea";
import { Label } from "@/components/label";
import { getPromptConfig, linkGoldSuite } from "@/services/promptEditor";
import {
  addTestCase,
  deleteTestCase,
  listTestCases,
  updateTestCase,
} from "@/services/testSuites";
import type { TestCase } from "@/interfaces/testSuite.interface";

interface GoldDatasetTabProps {
  workflowId: string;
  nodeId: string;
  promptField: string;
}

export const GoldDatasetTab: React.FC<GoldDatasetTabProps> = ({
  workflowId,
  nodeId,
  promptField,
}) => {
  const queryClient = useQueryClient();
  const configQueryKey = ["promptConfig", workflowId, nodeId, promptField];

  const [newInput, setNewInput] = useState("");
  const [newExpected, setNewExpected] = useState("");
  const [editingCaseId, setEditingCaseId] = useState<string | null>(null);
  const [editInput, setEditInput] = useState("");
  const [editExpected, setEditExpected] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: config, isLoading: configLoading } = useQuery({
    queryKey: configQueryKey,
    queryFn: () => getPromptConfig(workflowId, nodeId, promptField),
  });

  const suiteId = config?.gold_suite_id;

  const { data: cases = [], isLoading: casesLoading } = useQuery({
    queryKey: ["goldCases", suiteId],
    queryFn: () => listTestCases(suiteId!),
    enabled: !!suiteId,
    select: (data) => (data ?? []) as TestCase[],
  });

  const showError = (action: string, err: unknown) => {
    const message =
      err instanceof Error ? err.message : "Request failed (check permissions)";
    setError(`Failed to ${action}: ${message}`);
  };

  const createSuiteMutation = useMutation({
    mutationFn: async () => {
      setError(null);
      const result = await linkGoldSuite(workflowId, nodeId, promptField, {
        name: `Gold Dataset - ${nodeId}/${promptField}`,
      });
      if (!result) throw new Error("Server returned empty response — you may lack Evaluation permissions.");
      return result;
    },
    onSuccess: (data) => {
      // Directly update query cache for instant UI transition
      queryClient.setQueryData(configQueryKey, data);
    },
    onError: (err) => showError("create gold dataset", err),
  });

  const addCaseMutation = useMutation({
    mutationFn: async () => {
      setError(null);
      const result = await addTestCase(suiteId!, {
        input_data: { message: newInput },
        expected_output: { value: newExpected },
        tags: ["gold"],
      });
      if (!result) throw new Error("Server returned empty response.");
      return result;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["goldCases", suiteId] });
      setNewInput("");
      setNewExpected("");
    },
    onError: (err) => showError("add case", err),
  });

  const updateCaseMutation = useMutation({
    mutationFn: async (caseId: string) => {
      setError(null);
      const result = await updateTestCase(caseId, {
        input_data: { message: editInput },
        expected_output: { value: editExpected },
      });
      if (!result) throw new Error("Server returned empty response.");
      return result;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["goldCases", suiteId] });
      setEditingCaseId(null);
    },
    onError: (err) => showError("update case", err),
  });

  const deleteCaseMutation = useMutation({
    mutationFn: (caseId: string) => deleteTestCase(caseId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["goldCases", suiteId] });
    },
    onError: (err) => showError("delete case", err),
  });

  const startEditing = (tc: TestCase) => {
    setEditingCaseId(tc.id);
    setEditInput(tc.input_data?.message ?? JSON.stringify(tc.input_data));
    setEditExpected(tc.expected_output?.value ?? JSON.stringify(tc.expected_output));
  };

  if (configLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground">
        Loading...
      </div>
    );
  }

  if (!config) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-muted-foreground gap-3">
        <Database className="h-8 w-8" />
        <p>Could not load prompt config.</p>
        <p className="text-xs">You may not have Evaluation permissions, or the server returned an error.</p>
      </div>
    );
  }

  if (!suiteId) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-muted-foreground gap-3">
        <Database className="h-8 w-8" />
        <p>No gold dataset linked to this prompt</p>
        {error && (
          <div className="flex items-center gap-2 text-destructive text-sm bg-destructive/10 border border-destructive/20 rounded-md px-3 py-2 max-w-md">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}
        <Button
          onClick={() => createSuiteMutation.mutate()}
          disabled={createSuiteMutation.isPending}
        >
          <Plus className="h-4 w-4 mr-2" />
          {createSuiteMutation.isPending ? "Creating..." : "Create Gold Dataset"}
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4 pt-4">
      {error && (
        <div className="flex items-center gap-2 text-destructive text-sm bg-destructive/10 border border-destructive/20 rounded-md px-3 py-2">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}
      {/* Add new case form */}
      <div className="p-4 space-y-3 bg-gray-50">
        <p className="text-sm font-medium">Add Gold Case</p>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <Label className="text-xs">Input Message</Label>
            <Textarea
              value={newInput}
              onChange={(e) => setNewInput(e.target.value)}
              placeholder="User input message..."
              rows={3}
              className="text-sm"
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Expected Output</Label>
            <Textarea
              value={newExpected}
              onChange={(e) => setNewExpected(e.target.value)}
              placeholder="Expected assistant response..."
              rows={3}
              className="text-sm"
            />
          </div>
        </div>
        <Button
          size="sm"
          onClick={() => addCaseMutation.mutate()}
          disabled={!newInput.trim() || !newExpected.trim() || addCaseMutation.isPending}
        >
          <Plus className="h-4 w-4 mr-1" />
          {addCaseMutation.isPending ? "Adding..." : "Add Case"}
        </Button>
      </div>

      {/* Cases list */}
      {casesLoading ? (
        <div className="text-center py-4 text-muted-foreground text-sm">
          Loading cases...
        </div>
      ) : cases.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground text-sm">
          No gold cases yet. Add your first case above.
        </div>
      ) : (
        <div className="space-y-2">
          <p className="text-sm font-medium">{cases.length} Gold Case{cases.length !== 1 ? "s" : ""}</p>
          {cases.map((tc) => (
            <div key={tc.id} className="border rounded-lg p-3">
              {editingCaseId === tc.id ? (
                <div className="space-y-2">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <Label className="text-xs">Input</Label>
                      <Textarea
                        value={editInput}
                        onChange={(e) => setEditInput(e.target.value)}
                        rows={3}
                        className="text-sm"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Expected</Label>
                      <Textarea
                        value={editExpected}
                        onChange={(e) => setEditExpected(e.target.value)}
                        rows={3}
                        className="text-sm"
                      />
                    </div>
                  </div>
                  <div className="flex gap-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => updateCaseMutation.mutate(tc.id)}
                      disabled={updateCaseMutation.isPending}
                    >
                      <Check className="h-4 w-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setEditingCaseId(null)}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex items-start gap-3">
                  <div className="flex-1 grid grid-cols-2 gap-3 min-w-0">
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-1">Input</p>
                      <p className="text-sm line-clamp-3">
                        {tc.input_data?.message ?? JSON.stringify(tc.input_data)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-1">Expected</p>
                      <p className="text-sm line-clamp-3">
                        {tc.expected_output?.value ?? JSON.stringify(tc.expected_output)}
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-1 shrink-0">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0"
                      onClick={() => startEditing(tc)}
                    >
                      <Edit2 className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                      onClick={() => deleteCaseMutation.mutate(tc.id)}
                      disabled={deleteCaseMutation.isPending}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
