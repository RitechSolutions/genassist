/**
 * Frontend PCI (Payment Card Industry) redaction.
 *
 * Detects Primary Account Numbers (PANs / card numbers) in free text and
 * replaces them *before* the text ever leaves the browser. This is a
 * client-side complement to the backend redaction — the sensitive value is
 * scrubbed in-place so it is never rendered in the user's own message bubble
 * and never put on the wire.
 *
 * Detection is two-stage to keep false positives low:
 *   1. A regex finds candidate runs of 13–19 digits, allowing single spaces or
 *      dashes as group separators (e.g. "4111 1111 1111 1111", "4111-1111-...").
 *   2. Each candidate is confirmed with the Luhn checksum, so ordinary numbers
 *      (order IDs, phone numbers, dates, quantities) are left untouched.
 *
 * Note: CVV/CVC codes (3–4 digits) are intentionally NOT redacted. Without
 * surrounding context they are indistinguishable from any other short number
 * and would produce heavy false positives; the PAN is the element PCI DSS is
 * primarily concerned with protecting in transit.
 */

export const PCI_REDACTION_PLACEHOLDER = "[REDACTED]";

// A leading boundary (start-of-string or a non-digit, captured so it can be
// re-emitted), then 13–19 digits optionally grouped by single spaces/dashes,
// followed by a non-digit boundary. Avoiding look-behind keeps this compatible
// with every browser this embeddable widget can be dropped into.
const CARD_CANDIDATE_RE = /(^|[^\d])((?:\d[ -]?){12,18}\d)(?!\d)/g;

const MIN_PAN_LENGTH = 13;
const MAX_PAN_LENGTH = 19;

/**
 * Luhn (mod-10) checksum. Returns true when `digits` (a string of only 0-9)
 * is a valid card number per the Luhn algorithm.
 */
export function isLuhnValid(digits: string): boolean {
  if (digits.length === 0) return false;
  let sum = 0;
  let shouldDouble = false;
  for (let i = digits.length - 1; i >= 0; i--) {
    let d = digits.charCodeAt(i) - 48; // '0' === 48
    if (d < 0 || d > 9) return false;
    if (shouldDouble) {
      d *= 2;
      if (d > 9) d -= 9;
    }
    sum += d;
    shouldDouble = !shouldDouble;
  }
  return sum % 10 === 0;
}

/** True when the stripped digit string looks like a real PAN. */
function isCardNumber(digits: string): boolean {
  return (
    digits.length >= MIN_PAN_LENGTH &&
    digits.length <= MAX_PAN_LENGTH &&
    isLuhnValid(digits)
  );
}

/**
 * Returns true if `text` contains at least one Luhn-valid card number.
 * Useful for validation / warning UX without mutating the text.
 */
export function containsPci(text: string): boolean {
  if (!text) return false;
  CARD_CANDIDATE_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = CARD_CANDIDATE_RE.exec(text)) !== null) {
    const digits = match[2].replace(/[ -]/g, "");
    if (isCardNumber(digits)) return true;
  }
  return false;
}

/**
 * Replace every Luhn-valid card number in `text` with `placeholder`.
 * Non-card digit runs (phone numbers, IDs, dates, …) are left untouched.
 */
export function redactPci(
  text: string,
  placeholder: string = PCI_REDACTION_PLACEHOLDER,
): string {
  if (!text) return text;
  return text.replace(CARD_CANDIDATE_RE, (_full, lead: string, num: string) => {
    const digits = num.replace(/[ -]/g, "");
    return isCardNumber(digits) ? `${lead}${placeholder}` : `${lead}${num}`;
  });
}
