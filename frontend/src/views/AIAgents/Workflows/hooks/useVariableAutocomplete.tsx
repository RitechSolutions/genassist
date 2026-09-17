import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { VariableNode } from "@/helpers/variable-input/variableTree";
import {
  detectVariableTrigger,
  replaceTriggerWithReference,
  type VariableTrigger,
} from "@/helpers/variable-input/variableTrigger";
import {
  getCaretViewportPosition,
  type CaretViewportPosition,
} from "@/helpers/variable-input/caretCoordinates";
import { insertReferenceAt } from "@/helpers/variable-input/variableReference";
import { useWorkflowVariables } from "../context/WorkflowVariablesContext";
import {
  SUGGESTIONS_ATTRIBUTE,
  VariableSuggestions,
} from "../components/custom/VariableSuggestions";
import { useVariableTree } from "./useVariableTree";

type Field = HTMLInputElement | HTMLTextAreaElement;

const NAVIGATION_KEYS = ["ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight", "Enter", "Tab"];

interface UseVariableAutocompleteOptions<TEl extends Field> {
  elementRef: React.RefObject<TEl | null>;
  value: string;
  onChange: (e: React.ChangeEvent<TEl>) => void;
}

interface VariableAutocomplete<TEl extends Field> {
  /** Handlers to spread onto the field */
  fieldProps: {
    onChange: (e: React.ChangeEvent<TEl>) => void;
    onKeyUp: React.KeyboardEventHandler<TEl>;
    onClick: React.MouseEventHandler<TEl>;
    onBlur: React.FocusEventHandler<TEl>;
  };
  /** The caret-anchored popup, or null when closed */
  suggestions: React.ReactNode;
  /** Insert a variable at the last known caret, used by the picker button */
  insertVariable: (option: VariableNode) => void;
}

/**
 * Drives the "{{" typeahead inside an input or textarea: tracks the open
 * trigger, positions the tree at the caret and rewrites the value on select.
 */
export function useVariableAutocomplete<TEl extends Field>({
  elementRef,
  value,
  onChange,
}: UseVariableAutocompleteOptions<TEl>): VariableAutocomplete<TEl> {
  const { tree } = useWorkflowVariables();
  const [trigger, setTrigger] = useState<VariableTrigger | null>(null);
  const [anchor, setAnchor] = useState<CaretViewportPosition | null>(null);

  const triggerRef = useRef<VariableTrigger | null>(null);
  const caretRef = useRef<number | null>(null);

  const hasVariables = tree.length > 0;
  const query = trigger?.query ?? "";

  const { rows, activeIndex, setActiveIndex, toggle, handleKey } = useVariableTree(
    tree,
    query
  );

  // Opens even with no rows: an empty popup is what tells the user the node
  // has no upstream data, rather than "{{" appearing to do nothing at all.
  const isOpen = trigger !== null && anchor !== null;

  const close = useCallback(() => {
    triggerRef.current = null;
    setTrigger(null);
    setAnchor(null);
  }, []);

  // Re-evaluate the trigger whenever the value or the caret moves
  const sync = useCallback(
    (nextValue: string, caret: number) => {
      caretRef.current = caret;

      const found = detectVariableTrigger(nextValue, caret);
      if (!found) {
        if (triggerRef.current) close();
        return;
      }

      const previous = triggerRef.current;
      if (previous && previous.start === found.start && previous.query === found.query) {
        return;
      }

      triggerRef.current = found;
      setTrigger(found);

      const el = elementRef.current;
      // Anchor to the "{{" rather than the caret so the tree holds still
      if (el) setAnchor(getCaretViewportPosition(el, found.start));
    },
    [close, elementRef]
  );

  const syncFromElement = useCallback(() => {
    const el = elementRef.current;
    if (!el) return;
    sync(el.value, el.selectionStart ?? el.value.length);
  }, [elementRef, sync]);

  const applyValue = useCallback(
    (nextValue: string, cursor: number) => {
      close();
      onChange({ target: { value: nextValue } } as React.ChangeEvent<TEl>);

      // The field is controlled, so the caret can only be restored after re-render
      requestAnimationFrame(() => {
        const el = elementRef.current;
        if (!el) return;
        el.focus();
        el.setSelectionRange(cursor, cursor);
        caretRef.current = cursor;
      });
    },
    [close, onChange, elementRef]
  );

  /**
   * Inserts at the caret, replacing a half-typed "{{query" when one is there.
   * The trigger is re-read from the value rather than taken from state, so
   * opening the picker button (which blurs the field) still completes it.
   */
  const insertVariable = useCallback(
    (option: VariableNode) => {
      const el = elementRef.current;
      const current = el ? el.value : value ?? "";
      const focused = el != null && document.activeElement === el;
      const caret = focused
        ? el.selectionStart ?? current.length
        : Math.min(caretRef.current ?? current.length, current.length);

      const found = detectVariableTrigger(current, caret);
      const next = found
        ? replaceTriggerWithReference(current, found, option.reference, caret)
        : insertReferenceAt(current, option.reference, caret);

      applyValue(next.value, next.cursor);
    },
    [value, applyValue, elementRef]
  );

  // Radix listens for Escape with a capture listener on document, so the popup
  // has to claim its keys one phase earlier (on window) to keep the panel open.
  useEffect(() => {
    if (!isOpen) return;

    const handler = (event: KeyboardEvent) => {
      if (event.target !== elementRef.current) {
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
      // Left/right only belong to the tree while a branch is there to move on
      if (!handleKey(event.key, insertVariable)) return;

      event.preventDefault();
      event.stopImmediatePropagation();
    };

    window.addEventListener("keydown", handler, true);
    return () => window.removeEventListener("keydown", handler, true);
  }, [isOpen, handleKey, insertVariable, close, elementRef]);

  // The popup is anchored in viewport space, so an ancestor scroll strands it.
  // Its own wheel scrolling bubbles through the same capture listener, so
  // events coming from inside the popup have to be let through.
  useEffect(() => {
    if (!isOpen) return;

    const onScroll = (event: Event) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest?.(`[${SUGGESTIONS_ATTRIBUTE}]`)) return;
      close();
    };

    window.addEventListener("scroll", onScroll, true);
    window.addEventListener("resize", close);
    return () => {
      window.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("resize", close);
    };
  }, [isOpen, close]);

  const handleChange = useCallback(
    (e: React.ChangeEvent<TEl>) => {
      onChange(e);
      const el = e.target;
      sync(el.value, el.selectionStart ?? el.value.length);
    },
    [onChange, sync]
  );

  const fieldProps = useMemo(
    () => ({
      onChange: handleChange,
      onKeyUp: syncFromElement as React.KeyboardEventHandler<TEl>,
      onClick: syncFromElement as React.MouseEventHandler<TEl>,
      onBlur: ((e: React.FocusEvent<TEl>) => {
        caretRef.current = e.target.selectionStart ?? null;
        close();
      }) as React.FocusEventHandler<TEl>,
    }),
    [handleChange, syncFromElement, close]
  );

  return {
    fieldProps,
    insertVariable,
    suggestions:
      isOpen && anchor ? (
        <VariableSuggestions
          anchor={anchor}
          rows={rows}
          activeIndex={activeIndex}
          showBreadcrumb={query.length > 0}
          filtered={hasVariables}
          onSelect={insertVariable}
          onToggle={toggle}
          onHoverIndex={setActiveIndex}
        />
      ) : null,
  };
}
