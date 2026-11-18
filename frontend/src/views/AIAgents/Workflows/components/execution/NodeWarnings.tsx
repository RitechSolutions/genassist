import React from 'react';

interface NodeWarningsProps {
  warnings: string[];
}

/** Problems a node noted while still completing, such as a knowledge base it had to skip. */
const NodeWarnings: React.FC<NodeWarningsProps> = ({ warnings }) => {
  if (warnings.length === 0) return null;

  return (
    <div className="rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/15 dark:text-amber-400">
      <div className="mb-1 font-semibold uppercase tracking-wide">Warnings</div>
      {warnings.map((warning) => (
        <div key={warning} className="whitespace-pre-wrap break-words">
          {warning}
        </div>
      ))}
    </div>
  );
};

export default NodeWarnings;
