export interface DraftCheckpoint {
  content: string;
  label: string;
}

export interface DraftState {
  content: string;
  undo: DraftCheckpoint[];
  redo: DraftCheckpoint[];
}

export type DraftAction =
  | { type: "edit"; content: string }
  | { type: "apply"; content: string; label: string }
  | { type: "undo" }
  | { type: "redo" };

export const MAX_DRAFT_CHECKPOINTS = 20;

export const draftStateOf = (content: string): DraftState => ({
  content,
  undo: [],
  redo: [],
});

const push = (
  stack: DraftCheckpoint[],
  checkpoint: DraftCheckpoint,
): DraftCheckpoint[] => [...stack, checkpoint].slice(-MAX_DRAFT_CHECKPOINTS);

const step = (
  content: string,
  from: DraftCheckpoint[],
  to: DraftCheckpoint[],
): { content: string; from: DraftCheckpoint[]; to: DraftCheckpoint[] } | null => {
  const top = from[from.length - 1];
  if (!top) return null;
  return {
    content: top.content,
    from: from.slice(0, -1),
    to:
      top.content === content
        ? to
        : push(to, { content, label: top.label }),
  };
};

/** Returns the same state object when nothing changes */
export const draftReducer = (
  state: DraftState,
  action: DraftAction,
): DraftState => {
  switch (action.type) {
    case "edit":
      return action.content === state.content
        ? state
        : { ...state, content: action.content };
    case "apply":
      return action.content === state.content
        ? state
        : {
            content: action.content,
            undo: push(state.undo, {
              content: state.content,
              label: action.label,
            }),
            redo: [],
          };
    case "undo": {
      const next = step(state.content, state.undo, state.redo);
      return next
        ? { content: next.content, undo: next.from, redo: next.to }
        : state;
    }
    case "redo": {
      const next = step(state.content, state.redo, state.undo);
      return next
        ? { content: next.content, undo: next.to, redo: next.from }
        : state;
    }
  }
};
