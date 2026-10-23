import React from "react";

/** What the older methods had that no check can say yet. */
export const LeftOutNote: React.FC<{ items: string[] }> = ({ items }) => (
  <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-800 dark:text-amber-300">
    <p>These checks were made from the evaluation's older methods. Some settings have no check yet, so they were left out:</p>
    <ul className="mt-1 list-disc space-y-0.5 pl-5">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  </div>
);
