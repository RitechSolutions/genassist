export interface PricingNoticeCopy {
  lead: string;
  body: string;
  dismissLabel: string;
}

const COVERAGE_BODY =
  "Totals below are the priced subtotal. Rates added under LLM Settings › LLM Providers apply to new calls only.";
const FALLBACK_BODY = "Add matching rates to price new calls from your own configuration.";

export function pricingNoticeCopy(
  unpricedTokenPct: number,
  fallbackCalls: number,
  showCoverage: boolean,
  showFallback: boolean
): PricingNoticeCopy | null {
  const coverageLead = `${unpricedTokenPct.toFixed(1)}% of tokens have no configured rate`;
  const fallbackLead = `${fallbackCalls.toLocaleString()} calls used bundled fallback rates`;
  if (showCoverage && showFallback) {
    return { lead: `${coverageLead} and ${fallbackLead}.`, body: COVERAGE_BODY, dismissLabel: "Dismiss pricing notices" };
  }
  if (showCoverage) {
    return { lead: `${coverageLead}.`, body: COVERAGE_BODY, dismissLabel: "Dismiss pricing coverage notice" };
  }
  if (showFallback) {
    return { lead: `${fallbackLead}.`, body: FALLBACK_BODY, dismissLabel: "Dismiss fallback rates notice" };
  }
  return null;
}
