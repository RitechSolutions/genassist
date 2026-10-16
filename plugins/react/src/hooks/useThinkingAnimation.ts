import { useState, useEffect, useMemo } from 'react';
import { getTranslationArray, getTranslationString } from '../utils/i18n';
import type { ActivityKind, Translations } from '../types';

const ACTIVITY_LABEL_FALLBACKS: Record<ActivityKind, string> = {
  knowledge: 'Searching the knowledge base…',
  tool: 'Working on your request…',
};

export const MIN_LABEL_MS = 800;

export interface LabelPace {
  latest?: ActivityKind;
  shown?: ActivityKind;
  shownAt: number | null;
}

export const IDLE_PACE: LabelPace = { shownAt: null };

/** Moves the label towards the latest step once the shown one has been up for MIN_LABEL_MS. */
export function paceLabel(
  pace: LabelPace,
  activityKind: ActivityKind | undefined,
  now: number,
): LabelPace {
  if (pace.shownAt === null) return { latest: activityKind, shownAt: now };
  const latest = activityKind ?? pace.latest;
  if (latest !== pace.shown && now >= pace.shownAt + MIN_LABEL_MS) return { latest, shown: latest, shownAt: now };
  return latest === pace.latest ? pace : { ...pace, latest };
}

interface UseThinkingAnimationOptions {
  isAgentTyping: boolean;
  thinkingPhrases: string[] | undefined;
  thinkingDelayMs: number | undefined;
  translations: Translations;
  activityKind: ActivityKind | undefined;
}

export function useThinkingAnimation({
  isAgentTyping,
  thinkingPhrases,
  thinkingDelayMs,
  translations,
  activityKind,
}: UseThinkingAnimationOptions) {
  const DEFAULT_THINKING_MESSAGES = useMemo(
    () => getTranslationArray('thinking.messages', translations, [
      "Thinking…",
      "Analyzing your question…",
      "Searching knowledge…",
      "Pulling relevant info…",
      "Drafting the answer…",
      "Double‑checking details…",
      "Tying it together…",
      "Almost there…",
    ]),
    [translations]
  );

  const [currentThinkingParts, setCurrentThinkingParts] = useState<string[]>([]);
  const [currentThinkingPartIndex, setCurrentThinkingPartIndex] = useState(0);

  useEffect(() => {
    if (!isAgentTyping) {
      setCurrentThinkingParts([]);
      setCurrentThinkingPartIndex(0);
      return;
    }

    const list = (thinkingPhrases && thinkingPhrases.length > 0) ? thinkingPhrases : DEFAULT_THINKING_MESSAGES;
    const randomIndex = Math.floor(Math.random() * list.length);
    const selectedPhrase = list[randomIndex];

    const parts = selectedPhrase.includes('|')
      ? selectedPhrase.split('|').map(part => part.trim()).filter(part => part.length > 0)
      : [selectedPhrase.trim()];

    setCurrentThinkingParts(parts);
    setCurrentThinkingPartIndex(0);

    if (parts.length <= 1) return;

    const rotDelay = Math.max(250, thinkingDelayMs || 1000);
    const timeoutIds: ReturnType<typeof setTimeout>[] = [];

    for (let i = 1; i < parts.length; i++) {
      const timeoutId = setTimeout(() => {
        setCurrentThinkingPartIndex(i);
      }, rotDelay * i);
      timeoutIds.push(timeoutId);
    }

    return () => {
      timeoutIds.forEach(id => clearTimeout(id));
    };
  }, [isAgentTyping, thinkingPhrases, thinkingDelayMs]);

  const [pace, setPace] = useState<LabelPace>(IDLE_PACE);
  const [wakeCount, wake] = useState(0);

  useEffect(() => {
    if (!isAgentTyping) {
      setPace(IDLE_PACE);
      return;
    }
    const next = paceLabel(pace, activityKind, Date.now());
    if (next !== pace) {
      setPace(next);
      return;
    }
    if (pace.latest === pace.shown || pace.shownAt === null) return;
    const timeoutId = setTimeout(() => wake((n) => n + 1), pace.shownAt + MIN_LABEL_MS - Date.now());
    return () => clearTimeout(timeoutId);
  }, [isAgentTyping, activityKind, pace, wakeCount]);

  const shownKind = isAgentTyping ? pace.shown : undefined;
  const activityLabel = shownKind
    ? getTranslationString(`thinking.activity.${shownKind}`, translations, ACTIVITY_LABEL_FALLBACKS[shownKind])
    : undefined;

  return {
    currentThinkingParts,
    currentThinkingPartIndex,
    activityLabel,
  };
}
