/**
 * Measures where the caret sits inside an input/textarea so a popup can be
 * anchored to it. Neither element exposes caret geometry, so the value is
 * re-rendered into an off-screen mirror that copies every layout-affecting style.
 */

const MIRRORED_STYLES = [
  "boxSizing",
  "width",
  "height",
  "borderTopWidth",
  "borderRightWidth",
  "borderBottomWidth",
  "borderLeftWidth",
  "paddingTop",
  "paddingRight",
  "paddingBottom",
  "paddingLeft",
  "fontStyle",
  "fontVariant",
  "fontWeight",
  "fontStretch",
  "fontSize",
  "fontFamily",
  "lineHeight",
  "letterSpacing",
  "wordSpacing",
  "textIndent",
  "textTransform",
  "textAlign",
  "direction",
  "tabSize",
] as const

interface CaretCoordinates {
  /** Offset from the field's border box, before its own scroll is applied */
  top: number
  left: number
  /** Height of the caret's line box */
  height: number
}

function getCaretCoordinates(
  el: HTMLInputElement | HTMLTextAreaElement,
  position: number
): CaretCoordinates {
  const doc = el.ownerDocument
  const computed = window.getComputedStyle(el)
  const isInput = el.nodeName === "INPUT"

  const mirror = doc.createElement("div")
  const target = mirror.style as unknown as Record<string, string>
  const source = computed as unknown as Record<string, string>
  for (const prop of MIRRORED_STYLES) {
    target[prop] = source[prop]
  }

  mirror.style.position = "absolute"
  mirror.style.top = "0"
  mirror.style.left = "-9999px"
  mirror.style.visibility = "hidden"
  mirror.style.whiteSpace = isInput ? "pre" : "pre-wrap"
  mirror.style.overflowWrap = isInput ? "normal" : "break-word"

  if (isInput) {
    // A single-line field never wraps, so let the mirror grow past its width
    mirror.style.width = "auto"
    mirror.style.height = "auto"
    mirror.style.overflow = "hidden"
  } else {
    mirror.style.height = "auto"
    mirror.style.overflow = "hidden"
  }

  mirror.textContent = el.value.slice(0, position)

  // A zero-width marker would collapse, and trailing whitespace is dropped
  // without following content, so the marker always carries a real character.
  const marker = doc.createElement("span")
  marker.textContent = el.value.slice(position) || "."
  mirror.appendChild(marker)

  doc.body.appendChild(mirror)

  const top = marker.offsetTop + (parseInt(computed.borderTopWidth, 10) || 0)
  const left = marker.offsetLeft + (parseInt(computed.borderLeftWidth, 10) || 0)
  const height =
    marker.offsetHeight || parseInt(computed.lineHeight, 10) || el.offsetHeight

  mirror.remove()

  return { top, left, height }
}

export interface CaretViewportPosition {
  /** Viewport x of the caret */
  left: number
  /** Viewport y of the line below the caret */
  top: number
}

/** Caret position in viewport coordinates, clamped to the field's own box. */
export function getCaretViewportPosition(
  el: HTMLInputElement | HTMLTextAreaElement,
  position: number
): CaretViewportPosition {
  const rect = el.getBoundingClientRect()
  const caret = getCaretCoordinates(el, position)

  return {
    left: Math.min(
      rect.left + caret.left - el.scrollLeft,
      rect.right
    ),
    top: Math.min(
      rect.top + caret.top - el.scrollTop + caret.height,
      rect.bottom
    ),
  }
}
