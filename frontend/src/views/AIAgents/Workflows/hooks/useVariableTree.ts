import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getVisibleRows,
  type VariableNode,
  type VariableRow,
} from "@/helpers/variable-input/variableTree";

interface VariableTree {
  /** The lines to render, in order */
  rows: VariableRow[];
  activeIndex: number;
  setActiveIndex: (index: number) => void;
  toggle: (path: string) => void;
  /** Handles a navigation key; returns false when the key was not ours */
  handleKey: (key: string, onSelect: (node: VariableNode) => void) => boolean;
}

/**
 * Expansion and keyboard state for the variable tree, shared by the "{{"
 * typeahead and the per-field picker so both navigate identically.
 */
export function useVariableTree(
  tree: VariableNode[],
  query: string
): VariableTree {
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(new Set());
  const [activeIndex, setActiveIndex] = useState(0);

  const rows = useMemo(
    () => getVisibleRows(tree, expanded, query),
    [tree, expanded, query]
  );

  // Filtering can shrink the list out from under the highlight
  useEffect(() => {
    setActiveIndex((index) => (index >= rows.length ? 0 : index));
  }, [rows.length]);

  // A new query re-ranks everything, so start from the top again
  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  const toggle = useCallback((path: string) => {
    setExpanded((previous) => {
      const next = new Set(previous);
      if (!next.delete(path)) next.add(path);
      return next;
    });
  }, []);

  const setExpansion = useCallback((path: string, open: boolean) => {
    setExpanded((previous) => {
      if (previous.has(path) === open) return previous;
      const next = new Set(previous);
      if (open) next.add(path);
      else next.delete(path);
      return next;
    });
  }, []);

  const handleKey = useCallback(
    (key: string, onSelect: (node: VariableNode) => void): boolean => {
      if (rows.length === 0) return false;
      const current = rows[Math.min(activeIndex, rows.length - 1)];

      if (key === "ArrowDown") {
        setActiveIndex((i) => (i + 1) % rows.length);
        return true;
      }
      if (key === "ArrowUp") {
        setActiveIndex((i) => (i - 1 + rows.length) % rows.length);
        return true;
      }
      // Left/right fall through when there is nothing to open or close, so the
      // caret still moves normally inside the field being typed into.
      if (key === "ArrowRight") {
        if (!current.expandable || current.expanded) return false;
        setExpansion(current.node.path, true);
        return true;
      }
      if (key === "ArrowLeft") {
        if (!current.expanded) return false;
        setExpansion(current.node.path, false);
        return true;
      }
      if (key === "Enter" || key === "Tab") {
        onSelect(current.node);
        return true;
      }

      return false;
    },
    [rows, activeIndex, setExpansion]
  );

  return { rows, activeIndex, setActiveIndex, toggle, handleKey };
}
