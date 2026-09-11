/**
 * Moving a variable from the panel into a field by drag & drop.
 *
 * The payload uses a private type rather than text/plain or application/json,
 * so text dragged in from anywhere else is left to the browser's own handling
 * instead of being wrapped as a variable reference.
 */

import { formatVariableReference } from "./variableReference"

export const VARIABLE_DRAG_TYPE = "application/x-workflow-variable"

export function setVariableDragData(
  dataTransfer: DataTransfer,
  path: string
): void {
  dataTransfer.setData(VARIABLE_DRAG_TYPE, path)
  dataTransfer.effectAllowed = "copy"
}

/** Readable during dragover, where the payload itself is not exposed. */
export function isVariableDrag(dataTransfer: DataTransfer | null): boolean {
  if (!dataTransfer) return false
  return Array.from(dataTransfer.types).includes(VARIABLE_DRAG_TYPE)
}

export function readVariableReference(
  dataTransfer: DataTransfer
): string | null {
  const path = dataTransfer.getData(VARIABLE_DRAG_TYPE)
  return path ? formatVariableReference(path) : null
}

/** One clear pill under the cursor instead of a ghost of the whole row. */
export function applyVariableDragImage(
  dataTransfer: DataTransfer,
  reference: string
): void {
  const pill = document.createElement("div")
  pill.textContent = reference

  Object.assign(pill.style, {
    position: "absolute",
    top: "-9999px",
    left: "0",
    padding: "6px 12px",
    background: "#2563eb",
    color: "white",
    borderRadius: "9999px",
    fontSize: "12px",
    fontWeight: "500",
    whiteSpace: "nowrap",
    boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
    pointerEvents: "none",
    fontFamily: "inherit",
  })

  document.body.appendChild(pill)
  dataTransfer.setDragImage(pill, 0, 0)
  requestAnimationFrame(() => pill.remove())
}
