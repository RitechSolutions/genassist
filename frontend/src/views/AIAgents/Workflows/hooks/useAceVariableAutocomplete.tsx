import React, { useCallback, useEffect, useRef, useState } from "react";
import type { VariableNode } from "@/helpers/variable-input/variableTree";
import {
  detectVariableTrigger,
  type VariableTrigger,
} from "@/helpers/variable-input/variableTrigger";
import { useWorkflowVariables } from "../context/WorkflowVariablesContext";
import { VariableSuggestions } from "../components/custom/VariableSuggestions";
import { useVariableTree } from "./useVariableTree";

/* eslint-disable @typescript-eslint/no-explicit-any */

const NAVIGATION_KEYS = [
  "ArrowDown",
  "ArrowUp",
  "ArrowLeft",
  "ArrowRight",
  "Enter",
  "Tab",
];

interface Anchor {
  top: number;
  left: number;
}

interface AceVariableAutocomplete {
  /** Register the editor once react-ace has built it; returns a cleanup */
  attach: (editor: any) => () => void;
  /** The caret-anchored popup, or null when closed */
  suggestions: React.ReactNode;
  insertVariable: (node: VariableNode) => void;
}

/**
 * Gives the code editor the same variable tree the plain fields get, rather
 * than Ace's own completion list — which is flat, needs a prefix before it
 * opens, and has no room for nesting.
 */
export function useAceVariableAutocomplete(): AceVariableAutocomplete {
  const { tree } = useWorkflowVariables();
  const editorRef = useRef<any>(null);
  const [trigger, setTrigger] = useState<VariableTrigger | null>(null);
  const [anchor, setAnchor] = useState<Anchor | null>(null);

  const query = trigger?.query ?? "";
  const { rows, activeIndex, setActiveIndex, toggle, handleKey } = useVariableTree(
    tree,
    query
  );

  // Opens even with no rows, so an unconnected node says so rather than
  // looking like "{{" simply does nothing
  const isOpen = trigger !== null && anchor !== null;

  const close = useCallback(() => {
    setTrigger(null);
    setAnchor(null);
  }, []);

  const sync = useCallback(() => {
    const editor = editorRef.current;
    if (!editor) return;

    const pos = editor.getCursorPosition();
    const line = editor.session.getLine(pos.row) as string;
    const found = detectVariableTrigger(line, pos.column);
    if (!found) {
      close();
      return;
    }

    setTrigger((previous) =>
      previous && previous.start === found.start && previous.query === found.query
        ? previous
        : found
    );

    // Anchor under the "{{" so the tree holds still while the query is typed
    const { pageX, pageY } = editor.renderer.textToScreenCoordinates(
      pos.row,
      found.start
    );
    const next = { left: pageX, top: pageY + editor.renderer.lineHeight };
    setAnchor((previous) =>
      previous && previous.left === next.left && previous.top === next.top
        ? previous
        : next
    );
  }, [close]);

  const insertVariable = useCallback(
    (node: VariableNode) => {
      const editor = editorRef.current;
      if (!editor) return;

      const pos = editor.getCursorPosition();
      const line = editor.session.getLine(pos.row) as string;
      const found = detectVariableTrigger(line, pos.column);

      // Select the half-typed "{{query" so the insert replaces it
      if (found) {
        editor.selection.moveCursorTo(pos.row, found.start);
        editor.selection.selectTo(pos.row, pos.column);
      }

      close();
      editor.insert(node.reference);
      editor.focus();
    },
    [close]
  );

  const attach = useCallback(
    (editor: any) => {
      editorRef.current = editor;

      const onBlur = () => close();
      const onScroll = () => close();

      editor.on("change", sync);
      editor.on("blur", onBlur);
      editor.selection.on("changeCursor", sync);
      editor.session.on("changeScrollTop", onScroll);
      editor.session.on("changeScrollLeft", onScroll);

      return () => {
        editor.off("change", sync);
        editor.off("blur", onBlur);
        editor.selection.off("changeCursor", sync);
        editor.session.off("changeScrollTop", onScroll);
        editor.session.off("changeScrollLeft", onScroll);
        if (editorRef.current === editor) editorRef.current = null;
      };
    },
    [sync, close]
  );

  // Claimed on window capture so the keys never reach Ace's own key handling
  useEffect(() => {
    if (!isOpen) return;

    const handler = (event: KeyboardEvent) => {
      const editor = editorRef.current;
      const target = event.target as Node | null;
      if (!editor || !target || !editor.container.contains(target)) {
        close();
        return;
      }

      if (event.key === "Escape") {
        event.preventDefault();
        event.stopImmediatePropagation();
        close();
        return;
      }

      if (!NAVIGATION_KEYS.includes(event.key)) return;
      // Left/right fall through when there is no branch to open or close
      if (!handleKey(event.key, insertVariable)) return;

      event.preventDefault();
      event.stopImmediatePropagation();
    };

    window.addEventListener("keydown", handler, true);
    return () => window.removeEventListener("keydown", handler, true);
  }, [isOpen, handleKey, insertVariable, close]);

  return {
    attach,
    insertVariable,
    suggestions:
      isOpen && anchor ? (
        <VariableSuggestions
          anchor={anchor}
          rows={rows}
          activeIndex={activeIndex}
          showBreadcrumb={query.length > 0}
          filtered={tree.length > 0}
          onSelect={insertVariable}
          onToggle={toggle}
          onHoverIndex={setActiveIndex}
        />
      ) : null,
  };
}
