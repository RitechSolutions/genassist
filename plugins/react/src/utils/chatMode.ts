import type { GenAgentChatProps } from '../types';

type ChatMode = NonNullable<GenAgentChatProps['mode']>;

/**
 * Modes that render a launcher and open the conversation as a floating panel on demand.
 * Behaviour keyed on "is the panel open" (scroll anchoring, read reporting, Escape
 * handling, panel mount) applies to every one of them, not just `floating`.
 */
export const isLauncherMode = (mode: ChatMode | string | undefined): boolean =>
  mode === 'floating' || mode === 'spotlight';
