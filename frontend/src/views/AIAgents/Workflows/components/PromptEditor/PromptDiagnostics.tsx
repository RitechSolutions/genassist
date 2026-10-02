import React, { useMemo } from "react";
import {
  DIAGNOSTIC_MESSAGES,
  directPredecessorIds,
  fanInNote,
  readPromptBindings,
  scanBraceCandidates,
  unknownBindings,
  unknownDataNote,
} from "../../utils/templateVariableDiagnostics";
import { useWorkflowExecution } from "../../context/WorkflowExecutionContext";
import { useWorkflowVariables } from "../../context/WorkflowVariablesContext";

const INLINE_DIAGNOSTICS_MAX = 3;

interface PromptDiagnosticsProps {
  nodeId: string;
  value: string;
}

/** Advisory notes on the draft's {{variables}}. Renders nothing when the draft is clean */
export const PromptDiagnostics: React.FC<PromptDiagnosticsProps> = ({
  nodeId,
  value,
}) => {
  const { tree } = useWorkflowVariables();
  const { edges: workflowEdges } = useWorkflowExecution();

  const draftBindings = useMemo(() => readPromptBindings(value), [value]);
  const braceScan = useMemo(() => scanBraceCandidates(value), [value]);
  const availabilityNote = useMemo(
    () => unknownDataNote(unknownBindings(draftBindings, tree)),
    [draftBindings, tree],
  );
  const fanIn = useMemo(
    () => fanInNote(draftBindings, directPredecessorIds(nodeId, workflowEdges)),
    [draftBindings, nodeId, workflowEdges],
  );

  const findings = braceScan.findings;
  const shown = findings.slice(0, INLINE_DIAGNOSTICS_MAX);
  const hidden = findings.length - shown.length;
  if (findings.length === 0 && availabilityNote === null && fanIn === null)
    return null;

  return (
    <div className="space-y-1 text-xs">
      {shown.map((finding) => (
        <p
          key={`${finding.index}-${finding.kind}`}
          className="text-amber-700 dark:text-amber-400"
        >
          <code className="font-mono">{finding.text}</code>{" "}
          {DIAGNOSTIC_MESSAGES[finding.kind]}
        </p>
      ))}
      {braceScan.truncated ? (
        <p className="text-amber-700 dark:text-amber-400">…and more.</p>
      ) : (
        hidden > 0 && (
          <p className="text-amber-700 dark:text-amber-400">
            …and {hidden} more.
          </p>
        )
      )}
      {availabilityNote && (
        <p className="text-muted-foreground">{availabilityNote}</p>
      )}
      {fanIn && <p className="text-muted-foreground">{fanIn}</p>}
    </div>
  );
};
