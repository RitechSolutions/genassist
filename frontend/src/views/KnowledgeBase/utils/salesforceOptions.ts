export type ContentFormat = 'text' | 'markdown' | 'html';

const CONTENT_FORMATS: ContentFormat[] = ['text', 'markdown', 'html'];

/** Salesforce KB content format; the legacy allow_html_content flag maps to html. */
export const resolveSalesforceContentFormat = (extraMetadata?: Record<string, unknown>): ContentFormat => {
  const contentFormat = extraMetadata?.content_format as ContentFormat | undefined;
  if (contentFormat && CONTENT_FORMATS.includes(contentFormat)) return contentFormat;
  if (extraMetadata?.allow_html_content) return 'html';
  return 'text';
};
