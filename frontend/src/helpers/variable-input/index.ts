/**
 * The surface RichInput and RichTextarea consume. Everything else in this
 * folder is imported from its own module directly, so it is deliberately not
 * re-exported here.
 */

export { hasVariableSyntax } from "./templateVariableConstants"
export { parseValueToSegments } from "./templateVariableHighlight"
export { VariableOverlayContent } from "./VariableOverlayContent"
export {
  createVariableFocusHandler,
  createVariableKeyDownHandler,
  createVariableKeyUpHandler,
  createVariableMouseUpHandler,
} from "./templateVariableHandlers"
