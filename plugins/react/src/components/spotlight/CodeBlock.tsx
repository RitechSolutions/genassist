import React, { useEffect, useMemo, useRef, useState } from 'react';
import type { Components } from 'react-markdown';
import { Check, Copy } from 'lucide-react';
import { highlightCode } from './highlightCode';

async function copyText(text: string): Promise<boolean> {
  try {
    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // fall through to the legacy path (e.g. insecure context)
  }
  try {
    const el = document.createElement('textarea');
    el.value = text;
    el.setAttribute('readonly', '');
    el.style.position = 'fixed';
    el.style.opacity = '0';
    document.body.appendChild(el);
    el.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(el);
    return ok;
  } catch {
    return false;
  }
}

/** A fenced code block: language label, copy button, highlighted monospace body. */
export const CodeBlock: React.FC<{ code: string; language?: string }> = ({ code, language }) => {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const tokens = useMemo(() => highlightCode(code, language), [code, language]);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  const onCopy = async () => {
    if (!(await copyText(code))) return;
    setCopied(true);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setCopied(false), 1600);
  };

  return (
    <div className="gas-code">
      <div className="gas-code-head">
        <span className="gas-code-lang">{language || 'code'}</span>
        <button
          type="button"
          className={`gas-code-copy${copied ? ' gas-code-copy--done' : ''}`}
          onClick={onCopy}
          aria-label={copied ? 'Copied' : 'Copy code'}
          title={copied ? 'Copied' : 'Copy code'}
        >
          {copied ? <Check size={13} /> : <Copy size={13} />}
          <span>{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      <pre>
        <code>
          {tokens.map((t, i) => (t.type ? <span key={i} className={`gas-tok-${t.type}`}>{t.text}</span> : t.text))}
        </code>
      </pre>
    </div>
  );
};

/** Plain text of a react-markdown node's children. */
function textOf(node: React.ReactNode): string {
  if (node == null || typeof node === 'boolean') return '';
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(textOf).join('');
  if (React.isValidElement<{ children?: React.ReactNode }>(node)) return textOf(node.props.children);
  return '';
}

/**
 * Markdown overrides for spotlight: fenced code (``` blocks) renders as a CodeBlock.
 * A module constant so MarkdownMessage's memoisation stays effective.
 */
export const SPOTLIGHT_MARKDOWN: Components = {
  pre: ({ children }) => {
    const child = React.Children.toArray(children)[0];
    const className = React.isValidElement<{ className?: string }>(child) ? child.props.className || '' : '';
    const language = /language-([\w+#.-]+)/.exec(className)?.[1];
    return <CodeBlock code={textOf(child).replace(/\n$/, '')} language={language} />;
  },
};
