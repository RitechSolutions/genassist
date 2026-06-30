import { useState, useEffect, useMemo } from 'react';
import { getTranslationArray } from '../utils/i18n';
import type { Translations } from '../types';

interface UseThinkingAnimationOptions {
  isAgentTyping: boolean;
  thinkingPhrases: string[] | undefined;
  thinkingDelayMs: number | undefined;
  translations: Translations;
}

export function useThinkingAnimation({
  isAgentTyping,
  thinkingPhrases,
  thinkingDelayMs,
  translations,
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

  return {
    currentThinkingParts,
    currentThinkingPartIndex,
  };
}
