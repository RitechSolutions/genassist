export { hasVariableSyntax, TEMPLATE_VARIABLE_REGEX } from "./templateVariableConstants"
export { getVariableRanges, mergeRanges, type VariableRange } from "./templateVariableRanges"
export {
  snapCaretOutOfVariable,
  snapToVariableBoundary,
  removeVariableAtCursor,
  deleteSelectionWithVariables,
  findVariableAtPosition,
} from "./templateVariableCaret"
export {
  createVariableFocusHandler,
  createVariableKeyDownHandler,
  createVariableKeyUpHandler,
  createVariableMouseUpHandler,
} from "./templateVariableHandlers"
export { parseValueToSegments, type HighlightSegment } from "./templateVariableHighlight"
export { VariableOverlayContent } from "./VariableOverlayContent"
