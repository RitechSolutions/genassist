import React from "react";

/** Render inline formatting: **bold** and `code`. */
const renderInline = (line: string, key: number) => {
  // React JSX handles XSS escaping automatically — no manual escapeHtml needed.
  const parts = line.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return (
    <span key={key}>
      {parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong>;
        }
        if (part.startsWith("`") && part.endsWith("`")) {
          return (
            <code key={i} className="rounded bg-gray-100 px-1 py-0.5 text-xs font-mono text-[hsl(var(--brand-600))]">
              {part.slice(1, -1)}
            </code>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </span>
  );
};

/** Lightweight markdown-ish renderer for agent messages (bold, inline code, numbered lists, bullet lists). */
const FormattedText = ({ text }: { text: string }) => {
  const lines = text.split("\n");

  // Group consecutive list lines into <ol> or <ul>
  const elements: React.ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];

    if (/^\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\d+\.\s+/, ""));
        i++;
      }
      elements.push(
        <ol key={elements.length} className="list-decimal list-inside space-y-1 my-1">
          {items.map((item, j) => <li key={j}>{renderInline(item, j)}</li>)}
        </ol>
      );
    } else if (/^[-•]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^[-•]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^[-•]\s+/, ""));
        i++;
      }
      elements.push(
        <ul key={elements.length} className="list-disc list-inside space-y-1 my-1">
          {items.map((item, j) => <li key={j}>{renderInline(item, j)}</li>)}
        </ul>
      );
    } else if (line.trim() === "") {
      elements.push(<br key={elements.length} />);
      i++;
    } else {
      elements.push(<p key={elements.length} className="my-0.5">{renderInline(line, 0)}</p>);
      i++;
    }
  }

  return <div className="space-y-0.5">{elements}</div>;
};

export default FormattedText;
