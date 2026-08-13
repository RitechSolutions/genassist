import React, { useCallback, useEffect, useRef, useState } from "react";
import { NodeData } from "../types/nodes";
import { BaseNodeDialogProps } from "./base";

export interface NodeDialogState<T extends NodeData, V extends object> {
  /** Current in-progress field values (local edit state). */
  values: V;
  /** Replace the whole values object (use for multi-field updates in one handler). */
  setValues: React.Dispatch<React.SetStateAction<V>>;
  /** Update a single field by key. */
  setField: <K extends keyof V>(key: K, value: V[K]) => void;
  /**
   * Original node `data` overlaid with the in-progress edits (after `toPayload`, when
   * provided). Pass this as `NodeConfigPanel`'s `data` prop AND it is what `handleSave`
   * persists — keeping unsaved-changes detection and the save payload in lockstep.
   */
  merged: T;
  /** Persist `merged` via `onUpdate`, then `onClose`. */
  handleSave: () => void;
}

/**
 * Shared state/lifecycle for node configuration dialogs.
 *
 * Every node dialog repeats the same wrapper boilerplate:
 *   - seed local field state from `data`
 *   - re-seed whenever the panel (re)opens or the node data changes (`[isOpen, data]`)
 *   - build a live "merged" object ({ ...data, ...edits }) used both as the save payload
 *     and as `NodeConfigPanel`'s `data` prop (which powers unsaved-changes detection — so
 *     every editable field must be represented there)
 *   - save via `onUpdate(merged)` then `onClose()`
 *
 * This hook centralizes that behavior. It is opt-in and behavior-preserving: dialogs
 * migrate one at a time.
 *
 * Two forms:
 *   1. `useNodeDialogState(props, seed)` — `values` is a subset of the node data
 *      (`Partial<T>`); `merged = { ...data, ...values }`. Use when the save payload is a
 *      plain field merge.
 *   2. `useNodeDialogState(props, seed, toPayload)` — `values` may be any local edit shape
 *      (extra/intermediate keys, different names); `toPayload(values, data)` maps it to the
 *      persisted `Partial<T>`, and `merged = { ...data, ...toPayload(values, data) }`. Use
 *      for save-time transforms (empty→undefined, renamed keys, derived/parsed fields).
 *
 * @param props     Standard node-dialog props ({ isOpen, onClose, data, onUpdate, ... }).
 * @param seed      Returns the initial field values from the current `data`. Re-invoked on
 *                  every (re)open; the latest closure is always used, so it may read fresh
 *                  props/context without being memoized by the caller.
 * @param toPayload Optional: maps `values` to the node-data patch to merge & persist.
 */
export function useNodeDialogState<T extends NodeData, V extends Partial<T>>(
  props: BaseNodeDialogProps<T, T>,
  seed: () => V
): NodeDialogState<T, V>;
export function useNodeDialogState<T extends NodeData, V extends object>(
  props: BaseNodeDialogProps<T, T>,
  seed: () => V,
  toPayload: (values: V, data: T) => Partial<T>
): NodeDialogState<T, V>;
export function useNodeDialogState<T extends NodeData, V extends object>(
  props: BaseNodeDialogProps<T, T>,
  seed: () => V,
  toPayload?: (values: V, data: T) => Partial<T>
): NodeDialogState<T, V> {
  const { isOpen, data, onUpdate, onClose } = props;

  // Hold the latest closures so the re-seed effect can keep `[isOpen, data]` deps without
  // listing `seed`/`toPayload` (which get a new identity on every render).
  const seedRef = useRef(seed);
  seedRef.current = seed;
  const toPayloadRef = useRef(toPayload);
  toPayloadRef.current = toPayload;

  const [values, setValues] = useState<V>(() => seedRef.current());

  // Mirror the historical `useEffect(() => { if (isOpen) { ...re-seed... } }, [isOpen, data])`
  // present in every node dialog: re-seed on open and whenever the node data changes.
  useEffect(() => {
    if (isOpen) {
      setValues(seedRef.current());
    }
  }, [isOpen, data]);

  const setField = useCallback(<K extends keyof V>(key: K, value: V[K]) => {
    setValues((prev) => ({ ...prev, [key]: value }) as V);
  }, []);

  const patch = toPayloadRef.current
    ? toPayloadRef.current(values, data)
    : (values as unknown as Partial<T>);
  const merged = { ...data, ...patch } as T;

  const handleSave = () => {
    onUpdate(merged);
    onClose();
  };

  return { values, setValues, setField, merged, handleSave };
}
