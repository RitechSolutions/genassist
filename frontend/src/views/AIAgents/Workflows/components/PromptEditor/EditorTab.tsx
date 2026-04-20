import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, CheckCircle2, Loader2, Play, Sparkles, XCircle } from 'lucide-react';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/accordion';
import { Button } from '@/components/button';
import { Label } from '@/components/label';
import { Textarea } from '@/components/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/select';
import { Badge } from '@/components/badge';
import { Switch } from '@/components/switch';
import { getAllLLMProviders } from '@/services/llmProviders';
import { createPromptVersion, evaluatePrompt, getPromptConfig, optimizePrompt } from '@/services/promptEditor';
import { listTestCases } from '@/services/testSuites';
import type { LLMProvider } from '@/interfaces/llmProvider.interface';
import type { PromptEvalResponse, PromptOptimizeResponse } from '@/interfaces/promptEditor.interface';
import type { TestCase } from '@/interfaces/testSuite.interface';

interface EditorTabProps {
  workflowId: string;
  nodeId: string;
  promptField: string;
  value: string;
  onChange: (newValue: string) => void;
  defaultProviderId?: string;
}

export const EditorTab: React.FC<EditorTabProps> = ({
  workflowId,
  nodeId,
  promptField,
  value,
  onChange,
  defaultProviderId,
}) => {
  const queryClient = useQueryClient();

  const [error, setError] = useState<string | null>(null);
  const [warningMessage, setWarningMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [selectedProviderId, setSelectedProviderId] = useState(defaultProviderId || '');
  const [selectedTechniques, setSelectedTechniques] = useState<string[]>(['contains']);
  const [evalResults, setEvalResults] = useState<PromptEvalResponse | null>(null);
  const [optimizeResult, setOptimizeResult] = useState<PromptOptimizeResponse | null>(null);
  const [optimizedEvalResults, setOptimizedEvalResults] = useState<PromptEvalResponse | null>(null);
  const [optimizeInstructions, setOptimizeInstructions] = useState('');

  const TECHNIQUES = [
    { key: 'exact_match', label: 'Exact Match' },
    { key: 'contains', label: 'Contains' },
    { key: 'nli_eval', label: 'NLI Semantic Match' },
  ];

  const { data: providers = [] } = useQuery({
    queryKey: ['llmProviders'],
    queryFn: getAllLLMProviders,
    select: (data: LLMProvider[]) => data.filter((p) => p.is_active === 1),
  });

  const { data: promptConfig } = useQuery({
    queryKey: ['promptConfig', workflowId, nodeId, promptField],
    queryFn: () => getPromptConfig(workflowId, nodeId, promptField),
  });

  const goldSuiteId = promptConfig?.gold_suite_id;

  const { data: goldCases = [] } = useQuery({
    queryKey: ['goldCases', goldSuiteId],
    queryFn: () => listTestCases(goldSuiteId!),
    enabled: !!goldSuiteId,
    select: (data) => (data ?? []) as TestCase[],
  });

  const toggleTechnique = (key: string) => {
    setSelectedTechniques((prev) => (prev.includes(key) ? prev.filter((t) => t !== key) : [...prev, key]));
  };

  const showError = (action: string, err: unknown) => {
    const message = err instanceof Error ? err.message : 'Request failed';
    setError(`Failed to ${action}: ${message}`);
    setWarningMessage(null);
    setSuccessMessage(null);
  };

  const evalMutation = useMutation({
    mutationFn: async () => {
      setError(null);
      const result = await evaluatePrompt(workflowId, nodeId, promptField, {
        prompt_content: value,
        techniques: selectedTechniques,
        provider_id: selectedProviderId,
      });
      if (!result) throw new Error('Server returned empty response — check permissions.');
      return result;
    },
    onSuccess: (data) => {
      setEvalResults(data);
    },
    onError: (err) => showError('evaluate prompt', err),
  });

  const optimizeMutation = useMutation({
    mutationFn: async () => {
      setError(null);
      const result = await optimizePrompt(workflowId, nodeId, promptField, {
        provider_id: selectedProviderId,
        current_prompt: value,
        instructions: optimizeInstructions || undefined,
        failed_cases: evalResults?.results
          .filter((r) => !r.passed)
          .map((r) => ({
            input: r.input,
            expected: r.expected,
            actual: r.actual,
          })),
      });
      if (!result) throw new Error('Server returned empty response — check permissions.');
      return result;
    },
    onSuccess: (data) => {
      setOptimizeResult(data);
      setOptimizedEvalResults(null);
    },
    onError: (err) => showError('optimize prompt', err),
  });

  const evalOptimizedMutation = useMutation({
    mutationFn: async () => {
      if (!optimizeResult) return;
      setError(null);
      const result = await evaluatePrompt(workflowId, nodeId, promptField, {
        prompt_content: optimizeResult.suggested_prompt,
        techniques: selectedTechniques,
        provider_id: selectedProviderId,
      });
      if (!result) throw new Error('Server returned empty response — check permissions.');
      return result;
    },
    onSuccess: (data) => {
      if (data) setOptimizedEvalResults(data);
    },
    onError: (err) => showError('evaluate suggested prompt', err),
  });

  const acceptOptimizedMutation = useMutation({
    mutationFn: async () => {
      if (!optimizeResult) return;
      onChange(optimizeResult.suggested_prompt);
      await createPromptVersion(workflowId, nodeId, promptField, {
        content: optimizeResult.suggested_prompt,
        label: 'Optimized prompt',
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['promptVersions', workflowId, nodeId, promptField],
      });
      setOptimizeResult(null);
      setOptimizedEvalResults(null);
      setSuccessMessage('Optimized prompt accepted and saved as new version');
    },
    onError: (err) => showError('accept optimized prompt', err),
  });

  return (
    <div className="space-y-4 pt-4 px-2">
      {(error || warningMessage || successMessage) && (
        <div className="space-y-2">
          {error && (
            <div className="flex items-center gap-2 text-destructive text-sm bg-destructive/10 border border-destructive/20 rounded-md px-3 py-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
          {warningMessage && (
            <div className="flex items-center gap-2 text-amber-700 text-sm bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{warningMessage}</span>
            </div>
          )}
          {successMessage && (
            <div className="flex items-center gap-2 text-green-700 text-sm bg-green-50 border border-green-200 rounded-md px-3 py-2">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              <span>{successMessage}</span>
            </div>
          )}
        </div>
      )}

      <div className="space-y-2">
        <Label>LLM Provider</Label>
        <Select value={selectedProviderId} onValueChange={setSelectedProviderId}>
          <SelectTrigger className="w-full">
            <SelectValue placeholder="Select provider for evaluation/optimization" />
          </SelectTrigger>
          <SelectContent>
            {providers.map((provider) => (
              <SelectItem key={provider.id} value={provider.id}>
                {provider.name} ({provider.llm_model_provider} - {provider.llm_model})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label>Prompt Content</Label>
        <Textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Enter your prompt..."
          rows={10}
          className="w-full font-mono text-sm"
        />
        <div className="text-xs text-muted-foreground text-right">{value.length} characters</div>
      </div>

      <Accordion type="multiple" className="border rounded-lg px-4">
        <AccordionItem value="optimize">
          <AccordionTrigger className="hover:no-underline">
            <div className="flex items-center justify-between w-full pr-2">
              <span>Optimize Prompt</span>
              {optimizeResult && <span className="text-xs text-muted-foreground">Suggestion ready</span>}
            </div>
          </AccordionTrigger>
          <AccordionContent>
            <div className="space-y-4 flex flex-col gap-2">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">
                    Add optional guidance, then generate an improved prompt suggestion.
                  </p>
                </div>
              </div>

              <div className="space-y-2 px-2">
                <Label className="text-sm">Additional Instructions (optional)</Label>
                <Textarea
                  value={optimizeInstructions}
                  onChange={(e) => setOptimizeInstructions(e.target.value)}
                  placeholder="e.g., Make it more concise, add examples, enforce JSON output..."
                  rows={2}
                  className="text-sm"
                />
              </div>

              {optimizeResult && (
                <div className="space-y-3 border-t pt-4">
                  <div className="space-y-2">
                    <Label className="text-sm font-medium">Suggested Prompt</Label>
                    <div className="border rounded p-3 bg-gray-50 text-sm font-mono whitespace-pre-wrap max-h-48 overflow-y-auto">
                      {optimizeResult.suggested_prompt}
                    </div>
                  </div>
                  {optimizeResult.explanation && (
                    <div className="space-y-1">
                      <Label className="text-sm font-medium">Explanation</Label>
                      <p className="text-sm text-muted-foreground">{optimizeResult.explanation}</p>
                    </div>
                  )}

                  <div className="flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      onClick={() => evalOptimizedMutation.mutate()}
                      disabled={
                        !selectedProviderId || selectedTechniques.length === 0 || evalOptimizedMutation.isPending
                      }
                      variant="outline"
                    >
                      {evalOptimizedMutation.isPending ? (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      ) : (
                        <Play className="h-4 w-4 mr-2" />
                      )}
                      {evalOptimizedMutation.isPending ? 'Evaluating...' : 'Evaluate Suggested'}
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => acceptOptimizedMutation.mutate()}
                      disabled={acceptOptimizedMutation.isPending}
                    >
                      {acceptOptimizedMutation.isPending ? 'Accepting...' : 'Accept & Save as Version'}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setOptimizeResult(null);
                        setOptimizedEvalResults(null);
                      }}
                    >
                      Dismiss
                    </Button>
                  </div>

                  {optimizedEvalResults && (
                    <div className="space-y-3 border-t pt-3">
                      <div className="flex flex-wrap items-center gap-3">
                        <p className="text-sm font-medium">Suggested Prompt Evaluation</p>
                        <Badge variant="secondary">
                          {optimizedEvalResults.summary.passed}/{optimizedEvalResults.summary.total} passed
                        </Badge>
                        <Badge variant="secondary">
                          Avg Score: {(optimizedEvalResults.summary.avg_score * 100).toFixed(1)}%
                        </Badge>
                      </div>
                      <div className="space-y-2 max-h-60 overflow-y-auto">
                        {optimizedEvalResults.results.map((r, i) => (
                          <div
                            key={r.case_id || i}
                            className={`border rounded p-3 text-sm ${
                              r.passed ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'
                            }`}
                          >
                            <div className="flex items-center gap-2 mb-2">
                              {r.passed ? (
                                <CheckCircle2 className="h-4 w-4 text-green-600" />
                              ) : (
                                <XCircle className="h-4 w-4 text-red-600" />
                              )}
                              <span className="font-medium">{r.passed ? 'Passed' : 'Failed'}</span>
                            </div>
                            <div className="grid grid-cols-3 gap-2 text-xs">
                              <div>
                                <p className="font-medium text-muted-foreground">Input</p>
                                <p className="line-clamp-3">{r.input}</p>
                              </div>
                              <div>
                                <p className="font-medium text-muted-foreground">Expected</p>
                                <p className="line-clamp-3">{r.expected}</p>
                              </div>
                              <div>
                                <p className="font-medium text-muted-foreground">Actual</p>
                                <p className="line-clamp-3">{r.actual}</p>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <div className="flex justify-end">
                <Button
                  size="sm"
                  onClick={() => optimizeMutation.mutate()}
                  disabled={!selectedProviderId || !value.trim() || optimizeMutation.isPending}
                >
                  {optimizeMutation.isPending ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Sparkles className="h-4 w-4 mr-2" />
                  )}
                  {optimizeMutation.isPending ? 'Optimizing...' : 'Optimize'}
                </Button>
              </div>
            </div>
          </AccordionContent>
        </AccordionItem>

        <AccordionItem value="evaluate">
          <AccordionTrigger className="hover:no-underline">
            <div className="flex items-center justify-between w-full pr-2">
              <span>Evaluate Prompt</span>
              {evalResults && (
                <span className="text-xs text-muted-foreground">
                  {evalResults.summary.passed}/{evalResults.summary.total} passed
                </span>
              )}
            </div>
          </AccordionTrigger>
          <AccordionContent>
            <div className="space-y-4">
              <div className="flex flex-col gap-2">
                <div className="flex flex-wrap gap-2">
                  {TECHNIQUES.map((t) => (
                    <div key={t.key} className="flex items-center gap-2">
                      <Switch
                        checked={selectedTechniques.includes(t.key)}
                        onCheckedChange={() => toggleTechnique(t.key)}
                      />
                      <Label className="text-sm cursor-pointer">{t.label}</Label>
                    </div>
                  ))}
                </div>
                <div className="flex justify-end">
                  <Button
                    size="sm"
                    variant="default"
                    onClick={() => {
                      setWarningMessage(null);
                      if (!goldSuiteId || goldCases.length === 0) {
                        setWarningMessage(
                          'Missing Gold Dataset. Create a Gold Dataset and add at least one test case before running evaluation.',
                        );
                        return;
                      }
                      evalMutation.mutate();
                    }}
                    disabled={
                      !selectedProviderId || selectedTechniques.length === 0 || !value.trim() || evalMutation.isPending
                    }
                  >
                    {evalMutation.isPending ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <Play className="h-4 w-4 mr-2" />
                    )}
                    {evalMutation.isPending ? 'Evaluating...' : 'Run Evaluation'}
                  </Button>
                </div>
              </div>

              {evalResults && (
                <div className="space-y-3">
                  <div className="flex gap-3">
                    <Badge variant="secondary">
                      {evalResults.summary.passed}/{evalResults.summary.total} passed
                    </Badge>
                    <Badge variant="secondary">Avg Score: {(evalResults.summary.avg_score * 100).toFixed(1)}%</Badge>
                  </div>

                  <div className="space-y-2 max-h-60 overflow-y-auto">
                    {evalResults.results.map((r, i) => (
                      <div
                        key={r.case_id || i}
                        className={`border rounded p-3 text-sm ${
                          r.passed ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'
                        }`}
                      >
                        <div className="flex items-center gap-2 mb-2">
                          {r.passed ? (
                            <CheckCircle2 className="h-4 w-4 text-green-600" />
                          ) : (
                            <XCircle className="h-4 w-4 text-red-600" />
                          )}
                          <span className="font-medium">{r.passed ? 'Passed' : 'Failed'}</span>
                        </div>
                        <div className="grid grid-cols-3 gap-2 text-xs">
                          <div>
                            <p className="font-medium text-muted-foreground">Input</p>
                            <p className="line-clamp-3">{r.input}</p>
                          </div>
                          <div>
                            <p className="font-medium text-muted-foreground">Expected</p>
                            <p className="line-clamp-3">{r.expected}</p>
                          </div>
                          <div>
                            <p className="font-medium text-muted-foreground">Actual</p>
                            <p className="line-clamp-3">{r.actual}</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  );
};
