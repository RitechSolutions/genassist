import * as React from "react";

import {
  resolveTextareaSizing,
  type TextareaSizingProps,
} from "@/components/ui/textarea-sizing";

export type TextareaProps = Omit<React.ComponentProps<"textarea">, "size"> &
  TextareaSizingProps;

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, size, rows, ...props }, ref) => {
    const sizing = resolveTextareaSizing({ size, rows, className });

    return (
      <textarea
        rows={sizing.rows}
        spellCheck={sizing.spellCheck}
        className={sizing.className}
        ref={ref}
        {...props}
      />
    );
  }
);

Textarea.displayName = "Textarea";

export { Textarea };
