/** Mirrors backend: "*" grants all permissions */
export const hasPerm = (
  permissions: readonly string[],
  required: string,
): boolean => permissions.includes("*") || permissions.includes(required);

export interface PromptEditorCapabilities {
  /** update:evaluation grants save, delete, copy legacy, and link dataset */
  canEditPrompt: boolean;
  /** Authoring only; intentionally separate from evaluating */
  canOptimize: boolean;
  /** run:evaluation */
  canEvaluate: boolean;
  /** Gold cases on Workflow routes */
  canReadCases: boolean;
  /** update:workflow */
  canEditCases: boolean;
}

export const promptEditorCapabilities = (
  permissions: readonly string[],
): PromptEditorCapabilities => ({
  canEditPrompt: hasPerm(permissions, "update:evaluation"),
  canOptimize: hasPerm(permissions, "update:evaluation"),
  canEvaluate: hasPerm(permissions, "run:evaluation"),
  canReadCases: hasPerm(permissions, "read:workflow"),
  canEditCases: hasPerm(permissions, "update:workflow"),
});
