import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';

const sanitizeSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    a: [
      ...(Array.isArray(defaultSchema.attributes?.a) ? defaultSchema.attributes.a : ['href']),
      'target',
      'rel',
    ],
  },
};

export interface MarkdownMessageProps {
  text: string;
  style?: React.CSSProperties;
}

/**
 * - Auto-linkifies bare URLs (https://..., http://..., mailto:...).
 * - All external links open in a new tab with target="_blank" and rel="noopener noreferrer".
 * - No dangerouslySetInnerHTML without sanitization; uses rehype-sanitize.
 */
export const MarkdownMessage: React.FC<MarkdownMessageProps> = ({ text, style }) => {
  const baseStyle: React.CSSProperties = {
    whiteSpace: 'pre-wrap',
    lineHeight: 1.5,
    margin: 0,
    ...style,
  };

  return (
    <div style={baseStyle}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize(sanitizeSchema)]}
        components={{
          a: ({ href, children, ...props }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              {...props}
              style={{ color: 'inherit', textDecoration: 'underline', cursor: 'pointer' }}
            >
              {children}
            </a>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
};
