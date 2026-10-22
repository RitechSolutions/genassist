export interface SseFrame {
  event: string;
  data: string;
}

/** Returns a parser that turns response body chunks into complete server-sent event frames, holding back an unfinished tail. */
export function createSseParser(): (chunk: Uint8Array) => SseFrame[] {
  const decoder = new TextDecoder();
  let buffer = "";
  return (chunk) => {
    buffer += decoder.decode(chunk, { stream: true });
    const blocks = buffer.replace(/\r\n/g, "\n").split("\n\n");
    buffer = blocks.pop() ?? "";
    const frames: SseFrame[] = [];
    for (const block of blocks) {
      let event = "message";
      const data: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
      }
      if (data.length) frames.push({ event, data: data.join("\n") });
    }
    return frames;
  };
}
