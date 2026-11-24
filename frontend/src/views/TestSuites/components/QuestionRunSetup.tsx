import React from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/select";
import type { KnowledgeItemMinimal } from "@/interfaces/knowledge.interface";
import type { LLMProviderMinimal } from "@/interfaces/llmProvider.interface";
import { type RunNote, listPlaceholder } from "../helpers/questionRun";
import type { PickList, QuestionRunForm } from "../hooks/useQuestionRunDialog";

interface QuestionRunSetupProps {
  form: QuestionRunForm;
  onChange: (change: Partial<QuestionRunForm>) => void;
  knowledgeBases: PickList<KnowledgeItemMinimal>;
  providers: PickList<LLMProviderMinimal>;
  isSampleInvalid: boolean;
  /** What is known about the picked knowledge base's articles. */
  note: RunNote | null;
  /** Set when the count failed, to offer counting again. */
  onRecount?: () => void;
}

const Field: React.FC<{ label: string; htmlFor: string; hint?: string; children: React.ReactNode }> = ({
  label,
  htmlFor,
  hint,
  children,
}) => (
  <div className="space-y-1.5">
    <Label htmlFor={htmlFor}>{label}</Label>
    {children}
    {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
  </div>
);

const TryAgain: React.FC<{ onClick: () => void }> = ({ onClick }) => (
  <button type="button" className="underline underline-offset-2" onClick={onClick}>
    Try again
  </button>
);

/** Says a list could not be loaded, instead of showing it as empty. */
const ListLoadFailed: React.FC<{ what: string; onRetry: () => void }> = ({ what, onRetry }) => (
  <p className="text-xs text-destructive">
    The {what} could not be loaded. <TryAgain onClick={onRetry} />
  </p>
);

/** The three choices of a question-writing run, and what the run would cost. */
export const QuestionRunSetup: React.FC<QuestionRunSetupProps> = ({
  form,
  onChange,
  knowledgeBases,
  providers,
  isSampleInvalid,
  note,
  onRecount,
}) => (
  <div className="space-y-4">
    <Field label="Knowledge base" htmlFor="question-run-knowledge-base">
      <Select
        value={form.knowledgeBaseId}
        onValueChange={(knowledgeBaseId) => onChange({ knowledgeBaseId })}
        disabled={knowledgeBases.count === 0}
      >
        <SelectTrigger id="question-run-knowledge-base">
          <SelectValue
            placeholder={listPlaceholder(knowledgeBases, "Choose a knowledge base", "No knowledge bases yet")}
          />
        </SelectTrigger>
        <SelectContent>
          {knowledgeBases.items.map((knowledgeBase) => (
            <SelectItem key={knowledgeBase.id} value={knowledgeBase.id}>
              {knowledgeBase.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {knowledgeBases.hasFailed && (
        <ListLoadFailed what="knowledge bases" onRetry={knowledgeBases.reload} />
      )}
    </Field>

    <Field
      label="Model"
      htmlFor="question-run-model"
      hint="Writes the questions and judges which article answers each one."
    >
      <Select
        value={form.providerId}
        onValueChange={(providerId) => onChange({ providerId })}
        disabled={providers.count === 0}
      >
        <SelectTrigger id="question-run-model">
          <SelectValue placeholder={listPlaceholder(providers, "Choose a model", "No active models yet")} />
        </SelectTrigger>
        <SelectContent>
          {providers.items.map((provider) => (
            <SelectItem key={provider.id} value={provider.id}>
              {provider.name} ({provider.llm_model_provider} - {provider.llm_model})
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {providers.hasFailed && <ListLoadFailed what="models" onRetry={providers.reload} />}
    </Field>

    <Field
      label="Articles to use"
      htmlFor="question-run-articles"
      hint={
        isSampleInvalid
          ? undefined
          : "Leave empty to use every article. A number uses that many, picked at random."
      }
    >
      <Input
        id="question-run-articles"
        inputMode="numeric"
        placeholder="All"
        value={form.sampleText}
        aria-invalid={isSampleInvalid}
        onChange={(event) => onChange({ sampleText: event.target.value })}
      />
      {isSampleInvalid && (
        <p className="text-xs text-destructive">Enter a whole number above 0, or leave it empty.</p>
      )}
    </Field>

    {note && (
      <p
        className={`rounded-md border bg-muted/40 px-3 py-2 text-sm ${
          note.isProblem ? "text-destructive" : "text-muted-foreground"
        }`}
      >
        {note.text} {onRecount && <TryAgain onClick={onRecount} />}
      </p>
    )}
  </div>
);
