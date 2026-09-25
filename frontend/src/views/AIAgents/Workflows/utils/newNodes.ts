/**
 * Node types that display a "NEW" badge in the Available Nodes palette
 * (see NodePanel). To flag another node as new, add its `type` string here;
 * remove it once it's no longer new. The comment next to each entry is the
 * node's display label, for readability.
 */
export const NEW_NODE_TYPES = new Set<string>([
  "nlpNode", // Text Analysis
  "webScraperNode", // Web Scraper
  "htmlToImageNode", // HTML to Image
  "salesforceCaseNode", // Salesforce Case Creator
  "subAgentNode", // Sub-Agent
]);

/** Whether a node type should show the "NEW" badge in the palette. */
export const isNewNode = (type: string): boolean => NEW_NODE_TYPES.has(type);
