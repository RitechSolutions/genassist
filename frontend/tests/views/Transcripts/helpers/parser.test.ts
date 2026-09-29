import { describe, expect, it } from "vitest";
import {
  parseTranscription,
  getTranscriptPreview,
  groupTranscriptByConversation,
} from "@/views/Transcripts/helpers/parser";
import type { Transcript } from "@/interfaces/transcript.interface";

const asTranscript = (value: unknown): Transcript => value as Transcript;

describe("parseTranscription", () => {
  it("normalizes a transcription array with defaults", () => {
    const result = parseTranscription(
      asTranscript({
        transcription: [
          { speaker: "Agent", text: "hi", start_time: 1, type: "message" },
          {},
        ],
      })
    );
    expect(result).toEqual([
      { speaker: "Agent", start_time: 1, text: "hi", type: "message" },
      { speaker: "Unknown", start_time: 0, text: "", type: "message" },
    ]);
  });

  it("falls back to the transcript field when transcription is absent", () => {
    const result = parseTranscription(
      asTranscript({ transcript: [{ speaker: "B", text: "yo", start_time: 2 }] })
    );
    expect(result).toEqual([{ speaker: "B", start_time: 2, text: "yo" }]);
  });

  it("returns an empty array for missing or empty input", () => {
    expect(parseTranscription(asTranscript(null))).toEqual([]);
    expect(parseTranscription(asTranscript({}))).toEqual([]);
  });
});

describe("getTranscriptPreview", () => {
  it("returns a placeholder when there is nothing to show", () => {
    expect(getTranscriptPreview(asTranscript(null))).toBe(
      "No transcription available"
    );
    expect(getTranscriptPreview(asTranscript({ transcription: [] }))).toBe(
      "No transcription available"
    );
  });

  it("returns the first non-empty message text", () => {
    expect(
      getTranscriptPreview(
        asTranscript({
          transcription: [
            { speaker: "A", text: "", start_time: 0, type: "message" },
            { speaker: "B", text: "second", start_time: 1, type: "message" },
          ],
        })
      )
    ).toBe("second");
  });

  it("truncates long text at maxLength with an ellipsis", () => {
    expect(
      getTranscriptPreview(
        asTranscript({
          transcription: [
            { speaker: "A", text: "abcdefgh", start_time: 0, type: "message" },
          ],
        }),
        5
      )
    ).toBe("abcde...");
  });

  it("summarizes file attachments by name", () => {
    expect(
      getTranscriptPreview(
        asTranscript({
          transcription: [
            {
              speaker: "A",
              text: JSON.stringify({ name: "doc.pdf" }),
              start_time: 0,
              type: "file",
            },
          ],
        })
      )
    ).toBe("File attached: doc.pdf");
  });

  it("handles malformed file attachment payloads", () => {
    expect(
      getTranscriptPreview(
        asTranscript({
          transcription: [
            { speaker: "A", text: "not-json", start_time: 0, type: "file" },
          ],
        })
      )
    ).toBe("File attached");
  });
});

describe("groupTranscriptByConversation", () => {
  it("returns an empty array for no entries", () => {
    expect(groupTranscriptByConversation([])).toEqual([]);
  });

  it("merges consecutive turns from the same speaker", () => {
    expect(
      groupTranscriptByConversation([
        { speaker: "A", text: "a", start_time: 0 },
        { speaker: "A", text: "b", start_time: 1 },
        { speaker: "B", text: "c", start_time: 2 },
      ])
    ).toEqual([
      { speaker: "A", text: "a b", start_time: 0 },
      { speaker: "B", text: "c", start_time: 2 },
    ]);
  });

  it("skips entries without a speaker", () => {
    expect(
      groupTranscriptByConversation([
        { speaker: "", text: "ignored", start_time: 0 },
        { speaker: "A", text: "kept", start_time: 1 },
      ])
    ).toEqual([{ speaker: "A", text: "kept", start_time: 1 }]);
  });
});
