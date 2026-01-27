import { ChatContentBlock, DynamicChatItem, FileItem, ScheduleItem } from "../types";

type MatchRecord = {
  start: number;
  end: number;
  type: "json" | "options" | "file";
  content: string;
};

const jsonBlockRegex = /```json\s*([\s\S]*?)\s*```/g;
const optionsRegex = /\*\*\*(.*?)\*\*\*/g;

const isDynamicChatItem = (value: any): value is DynamicChatItem => {
  return Boolean(
    value &&
    typeof value === "object" &&
    typeof value.id === "string" &&
    typeof value.name === "string"
  );
};

const isScheduleItem = (value: any): value is ScheduleItem => {
  return Boolean(
    value &&
    typeof value === "object" &&
    typeof value.id === "string" &&
    Array.isArray((value as any).restaurants)
  );
};

const isFileItem = (value: any): value is FileItem => {
  return Boolean(
    value &&
    typeof value === "object" &&
    typeof value.url === "string" &&
    typeof value.type === "string" &&
    typeof value.name === "string" &&
    typeof value.id === "string"
  );
};

const parseJsonBlock = (jsonString: string): ChatContentBlock | null => {
  try {
    const parsed = JSON.parse(jsonString);
    if (isScheduleItem(parsed)) {
      return { kind: "schedule", schedule: parsed };
    }
    if (Array.isArray(parsed) && parsed.every(isDynamicChatItem)) {
      return { kind: "items", items: parsed };
    }
  } catch (_error) {
    // ignore malformed JSON blocks
  }
  return null;
};

export const parseInteractiveContentBlocks = (
  text: string,
  messageType?: 'message' | 'file'
): ChatContentBlock[] => {
  const matches: MatchRecord[] = [];

  // case: file item or message type is file
  if (isFileItem(text) || messageType && messageType === 'file') {
    const cleanJson = text.replace(/\\/g, '');
    return [{ kind: "file", data: JSON.parse(cleanJson) as FileItem }];
  }

  jsonBlockRegex.lastIndex = 0;
  let jsonMatch: RegExpExecArray | null;
  while ((jsonMatch = jsonBlockRegex.exec(text)) !== null) {
    const fullMatch = jsonMatch[0];
    const content = jsonMatch[1];
    if (typeof jsonMatch.index !== "number" || !content) continue;
    matches.push({
      start: jsonMatch.index,
      end: jsonMatch.index + fullMatch.length,
      type: "json",
      content,
    });
  }

  optionsRegex.lastIndex = 0;
  let optionsMatch: RegExpExecArray | null;
  while ((optionsMatch = optionsRegex.exec(text)) !== null) {
    const fullMatch = optionsMatch[0];
    const content = optionsMatch[1];
    if (typeof optionsMatch.index !== "number" || !content) continue;
    matches.push({
      start: optionsMatch.index,
      end: optionsMatch.index + fullMatch.length,
      type: "options",
      content,
    });
  }

  if (matches.length === 0) {
    const trimmed = text.trim();
    return trimmed ? [{ kind: "text", text: trimmed }] : [];
  }

  matches.sort((a, b) => a.start - b.start);

  const blocks: ChatContentBlock[] = [];
  let lastIndex = 0;

  matches.forEach((match) => {
    if (lastIndex < match.start) {
      const before = text.slice(lastIndex, match.start).trim();
      if (before) {
        blocks.push({ kind: "text", text: before });
      }
    }

    if (match.type === "json") {
      const block = parseJsonBlock(match.content);
      if (block) {
        blocks.push(block);
      }
    } else {
      const options = match.content
        .split(";")
        .map((opt) => opt.trim())
        .filter(Boolean);
      if (options.length) {
        blocks.push({ kind: "options", options });
      }
    }

    lastIndex = match.end;
  });

  if (lastIndex < text.length) {
    const after = text.slice(lastIndex).trim();
    if (after) {
      blocks.push({ kind: "text", text: after });
    }
  }

  return blocks;
};

export const generateMessageContent = (blocks: ChatContentBlock[]): string => {
  let content = "";

  blocks.forEach((block) => {
    switch (block.kind) {
      case "text":
        content += block.text;
        break;
      case "items":
        content += `\`\`\`json\n${JSON.stringify(block.items)}\n\`\`\``;
        break;
      case "schedule":
        content += `\`\`\`json\n${JSON.stringify(block.schedule)}\n\`\`\``;
        break;
      case "options":
        content += `***${block.options.join("; ")}***`;
        break;
      default:
        break;
    }
  });

  return content;
};
