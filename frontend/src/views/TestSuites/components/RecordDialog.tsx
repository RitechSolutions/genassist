import React from "react";
import { CRUDDialog } from "@/components/ui/crud-dialog";
import { Label } from "@/components/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger } from "@/components/tabs";
import type { TestCase } from "@/interfaces/testSuite.interface";
import {
  answerOf,
  answerToExpected,
  isPlainRecord,
  parseRecordObject,
  questionOf,
  questionToInput,
} from "../helpers/recordFields";

export interface RecordPayload {
  input_data: Record<string, unknown>;
  expected_output: Record<string, unknown> | null;
}

interface RecordDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The turn to edit; null adds a new one. */
  record?: TestCase | null;
  /** The new turn opens a conversation rather than joining an existing one. */
  startsConversation?: boolean;
  onSubmit: (payload: RecordPayload) => Promise<void>;
}

interface Values {
  mode: string;
  question: string;
  answer: string;
  inputJson: string;
  expectedJson: string;
  [key: string]: unknown;
}

export const RecordDialog: React.FC<RecordDialogProps> = ({
  open,
  onOpenChange,
  record,
  startsConversation,
  onSubmit,
}) => {
  const isEdit = !!record;
  // A structured turn opens on JSON so its shape can never be silently flattened.
  const plainMode =
    !record || isPlainRecord(record.input_data, record.expected_output)
      ? "text"
      : "json";

  const editValues: Partial<Values> | null = record
    ? {
        mode: plainMode,
        question: questionOf(record.input_data) ?? "",
        answer: answerOf(record.expected_output) ?? "",
        inputJson: JSON.stringify(record.input_data ?? {}, null, 2),
        expectedJson: record.expected_output
          ? JSON.stringify(record.expected_output, null, 2)
          : "",
      }
    : null;

  return (
    <CRUDDialog<Values>
      open={open}
      onOpenChange={onOpenChange}
      mode={isEdit ? "edit" : "create"}
      maxWidth="640px"
      resetKey={isEdit ? (record?.id ?? null) : "create"}
      initialValues={{
        mode: "text",
        question: "",
        answer: "",
        inputJson: "",
        expectedJson: "",
      }}
      editValues={editValues}
      title={{
        create: startsConversation ? "New Conversation" : "Add Turn",
        edit: "Edit Turn",
      }}
      description={{
        create: startsConversation
          ? "Write the first turn. You can add more to this conversation afterwards."
          : "",
        edit: "",
      }}
      submitLabel={{
        create: startsConversation ? "Create Conversation" : "Add Turn",
        edit: "Save Changes",
      }}
      loadingLabel={{ create: "Adding...", edit: "Saving..." }}
      successMessage={{
        create: startsConversation ? "Conversation created." : "Turn added.",
        edit: "Turn updated.",
      }}
      errorMessage="Failed to save the turn."
      errorDisplay="both"
      submitDisabled={(form) => {
        if (form.values.mode === "text") return !form.values.question.trim();
        // Mirrors the text rule: an input with no content is not a turn.
        const input = parseRecordObject(form.values.inputJson);
        return !input.ok || Object.keys(input.value ?? {}).length === 0;
      }}
      validate={(values) => {
        if (values.mode === "text") return null;
        const input = parseRecordObject(values.inputJson);
        const expected = values.expectedJson.trim()
          ? parseRecordObject(values.expectedJson)
          : { ok: true as const };
        if (input.ok && expected.ok) return null;
        return {
          inputJson: input.ok ? undefined : input.error,
          expectedJson: expected.ok ? undefined : expected.error,
        };
      }}
      onSubmit={async (values) => {
        if (values.mode === "text") {
          await onSubmit({
            input_data: questionToInput(values.question),
            expected_output: answerToExpected(values.answer) ?? null,
          });
          return;
        }
        const input = parseRecordObject(values.inputJson);
        const expected = values.expectedJson.trim()
          ? parseRecordObject(values.expectedJson)
          : null;
        await onSubmit({
          input_data: input.value ?? {},
          expected_output: expected?.value ?? null,
        });
      }}
    >
      {(form) => {
        const isText = form.values.mode === "text";

        // Switching converts, so whichever panel is showing is the turn.
        // An empty field converts to an empty box, not to an empty wrapper —
        // {"message":""} is a turn with no user message, and {"value":""} is
        // an expected reply that exists but says nothing. The placeholders
        // teach the shape instead.
        const showJson = () => {
          const question = form.values.question;
          const expected = answerToExpected(form.values.answer);
          form.setField(
            "inputJson",
            question.trim()
              ? JSON.stringify(questionToInput(question), null, 2)
              : "",
          );
          form.setField(
            "expectedJson",
            expected ? JSON.stringify(expected, null, 2) : "",
          );
          form.setField("mode", "json");
        };

        // What the JSON draft would become as text, or null when text cannot
        // hold it. A blank box converts to a blank field — there is nothing to
        // lose — which is also what makes clearing the JSON a way back.
        const asPlainText = (): { question: string; answer: string } | null => {
          const read = (
            raw: string,
            extract: (obj: Record<string, unknown>) => string | null,
          ): string | null => {
            if (!raw.trim()) return "";
            const parsed = parseRecordObject(raw);
            if (!parsed.ok || !parsed.value) return null;
            return extract(parsed.value);
          };
          const question = read(form.values.inputJson, questionOf);
          if (question === null) return null;
          const answer = read(form.values.expectedJson, answerOf);
          return answer === null ? null : { question, answer };
        };

        const plainDraft = isText ? null : asPlainText();

        const showText = () => {
          if (!plainDraft) return;
          form.setField("question", plainDraft.question);
          form.setField("answer", plainDraft.answer);
          form.setField("mode", "text");
        };
        return (
          <>
            <Tabs
              value={form.values.mode}
              onValueChange={(next) => (next === "json" ? showJson() : showText())}
            >
              <TabsList>
                <TabsTrigger value="text" type="button" disabled={!isText && !plainDraft}>
                  Text
                </TabsTrigger>
                <TabsTrigger value="json" type="button">
                  JSON
                </TabsTrigger>
              </TabsList>
            </Tabs>

            {/* Both panels stay mounted so a draft survives switching. */}
            <div className={isText ? "space-y-5" : "hidden"}>
              <div className="space-y-2">
                <Label className="text-xs">User message</Label>
                <Textarea
                  value={form.values.question}
                  onChange={(e) => form.setField("question", e.target.value)}
                  rows={4}
                  placeholder="My order hasn't arrived yet."
                />
                <p className="text-xs text-muted-foreground">
                  What the user says to the agent.
                </p>
              </div>
              <div className="space-y-2">
                <Label className="text-xs">Expected reply</Label>
                <Textarea
                  value={form.values.answer}
                  onChange={(e) => form.setField("answer", e.target.value)}
                  rows={4}
                  placeholder="Let me check the tracking for you."
                />
                <p className="text-xs text-muted-foreground">
                  Leave blank only when rules score this turn. Text scorers
                  count an empty expected reply as a failure.
                </p>
              </div>
            </div>

            <div className={isText ? "hidden" : "space-y-5"}>
              {plainMode === "json" && (
                <p className="rounded-md border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-xs text-amber-700 dark:text-amber-500">
                  This turn holds more than a plain question and answer, so
                  it is shown as JSON to keep its shape intact.
                </p>
              )}
              <div className="space-y-2">
                <Label className="text-xs">Input</Label>
                <Textarea
                  value={form.values.inputJson}
                  onChange={(e) => form.setField("inputJson", e.target.value)}
                  rows={7}
                  placeholder={'{"message": "My order hasn\'t arrived yet."}'}
                  className="font-mono text-xs"
                />
                {form.errors.inputJson ? (
                  <p className="text-xs text-red-500">{form.errors.inputJson}</p>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    Needs a string <code>message</code>. The agent fails to run
                    without one.
                  </p>
                )}
              </div>
              <div className="space-y-2">
                <Label className="text-xs">Expected Output</Label>
                <Textarea
                  value={form.values.expectedJson}
                  onChange={(e) => form.setField("expectedJson", e.target.value)}
                  rows={7}
                  placeholder={'{"value": "Let me check the tracking for you."}'}
                  className="font-mono text-xs"
                />
                {form.errors.expectedJson ? (
                  <p className="text-xs text-red-500">
                    {form.errors.expectedJson}
                  </p>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    Only a lone <code>value</code> or <code>text</code> key is
                    compared as text; any other shape is matched as raw JSON.
                  </p>
                )}
              </div>
              {!plainDraft && (
                <p className="text-xs text-muted-foreground">
                  Text mode holds only a lone <code>message</code> and a lone{" "}
                  <code>value</code>. Simplify or clear these fields to switch
                  back without dropping anything.
                </p>
              )}
            </div>
          </>
        );
      }}
    </CRUDDialog>
  );
};

export default RecordDialog;
