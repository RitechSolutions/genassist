import { describe, expect, it } from "vitest";

import { createSseParser } from "./sse";

const encoder = new TextEncoder();

function parseChunks(chunks: string[]) {
  const parse = createSseParser();
  return chunks.flatMap((chunk) => parse(encoder.encode(chunk)));
}

describe("createSseParser", () => {
  it("keeps a frame split mid-line until its blank line arrives", () => {
    const frames = parseChunks(['event: activity\ndata: {"kind":"kno', 'wledge","phase":"start"}\n', "\n"]);

    expect(frames).toEqual([{ event: "activity", data: '{"kind":"knowledge","phase":"start"}' }]);
  });

  it("joins multi-line data with newlines", () => {
    const frames = parseChunks(["event: done\ndata: line one\ndata: line two\n\n"]);

    expect(frames).toEqual([{ event: "done", data: "line one\nline two" }]);
  });

  it("skips keepalive comments and id lines", () => {
    const frames = parseChunks([": ping\n\n", "id: 7\nevent: done\ndata: {}\n\n"]);

    expect(frames).toEqual([{ event: "done", data: "{}" }]);
  });

  it("accepts CRLF line endings, even split across chunks", () => {
    const frames = parseChunks(["event: done\r\ndata: {}\r", "\n\r\n"]);

    expect(frames).toEqual([{ event: "done", data: "{}" }]);
  });

  it("holds back an unfinished trailing frame", () => {
    const frames = parseChunks(["event: done\ndata: {}\n\nevent: error\ndata: {"]);

    expect(frames).toEqual([{ event: "done", data: "{}" }]);
  });
});
