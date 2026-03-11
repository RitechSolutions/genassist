import React from "react";
import { RichTextEditor } from "@/components/RichTextEditor";

interface DisclaimerEditorProps {
  value: string;
  onChange: (html: string) => void;
}

/**
 * Disclaimer-specific rich text editor.
 * Only exposes bold, font-size, and link formatting.
 */
export const DisclaimerEditor: React.FC<DisclaimerEditorProps> = ({
  value,
  onChange,
}) => (
  <RichTextEditor
    value={value}
    onChange={onChange}
    toolbar={{ bold: true, fontSize: true, link: true }}
    placeholder="e.g. Agent can make mistakes. <a href='...'>Learn more</a>"
  />
);
