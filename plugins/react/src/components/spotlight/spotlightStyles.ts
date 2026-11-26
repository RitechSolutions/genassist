/**
 * Stylesheet for mode="spotlight". Everything is scoped under `.gas-root` and reads the
 * theme through CSS custom properties (see buildSpotlightVars), so hover/focus states,
 * transitions, media queries and dark themes work without inline-style juggling.
 *
 * Motion: short, eased, transform/opacity only. All of it collapses to ~instant under
 * prefers-reduced-motion (durations are shortened rather than removed, so the
 * animationend that unmounts the closing panel still fires).
 */
export const SPOTLIGHT_CSS = `
.gas-root {
  display: contents;
  --gas-ease: cubic-bezier(0.22, 1, 0.36, 1);
  --gas-spring: cubic-bezier(0.34, 1.36, 0.64, 1);
  --gas-hover: color-mix(in srgb, var(--gas-text) 7%, transparent);
  --gas-hover-strong: color-mix(in srgb, var(--gas-text) 12%, transparent);
  --gas-edge: 0 0 0 1px color-mix(in srgb, var(--gas-border) 85%, transparent);
  --gas-shadow-lg: 0 10px 30px rgba(15, 23, 42, 0.12), 0 2px 6px rgba(15, 23, 42, 0.06);
  --gas-shadow-md: 0 4px 12px rgba(15, 23, 42, 0.08), var(--gas-edge);
  --gas-shadow-sm: 0 1px 3px rgba(15, 23, 42, 0.08), var(--gas-edge);
}
.gas-root *, .gas-root *::before, .gas-root *::after { box-sizing: border-box; }
.gas-root button { font-family: inherit; }
.gas-root :focus-visible { outline: 2px solid color-mix(in srgb, var(--gas-primary) 70%, transparent); outline-offset: 2px; }
/* Text fields sit inside their own pill (composer, teaser) — no focus outline of their own. */
.gas-root input[type="text"]:focus-visible, .gas-root input:not([type]):focus-visible, .gas-root textarea:focus-visible { outline: none; }

/* ===== Panel ===== */
.gas-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  background: var(--gas-surface);
  color: var(--gas-text);
  font-family: var(--gas-font);
  font-size: var(--gas-fs);
  border-radius: 28px;
  border: 1px solid color-mix(in srgb, var(--gas-border) 70%, transparent);
  box-shadow: var(--gas-shadow-lg);
}
.gas-panel--full { border-radius: 0; border: none; box-shadow: none; }
/* Fullscreen on a wide screen: keep a comfortable reading column. */
.gas-panel--full .gas-scroll,
.gas-panel--full .gas-footer {
  padding-left: max(18px, calc((100% - 780px) / 2));
  padding-right: max(18px, calc((100% - 780px) / 2));
}
.gas-panel--full .gas-sheet { left: max(12px, calc((100% - 780px) / 2)); right: max(12px, calc((100% - 780px) / 2)); }
@keyframes gas-panel-in {
  from { opacity: 0; transform: translateY(18px) scale(0.94); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}
@keyframes gas-panel-out {
  from { opacity: 1; transform: translateY(0) scale(1); }
  to   { opacity: 0; transform: translateY(14px) scale(0.96); }
}
/* backwards (not both): no transform at rest, so it never becomes a containing block
   for the fixed-position fullscreen panel. */
.gas-panel-in  { animation: gas-panel-in 380ms var(--gas-spring) backwards; }
.gas-panel-out { animation: gas-panel-out 200ms cubic-bezier(0.4, 0, 1, 1) both; }

/* ===== Header ===== */
.gas-header {
  position: absolute;
  top: 0; left: 0; right: 0;
  z-index: 6;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 12px 12px 0;
  pointer-events: none;
}
/* Frosted band behind the header: content scrolling underneath blurs (strongest at the
   top, easing out downward) under a light tint of the panel colour. */
.gas-header::before {
  content: '';
  position: absolute;
  left: 0; right: 0; top: 0;
  height: 84px;
  z-index: -1;
  pointer-events: none;
  background: linear-gradient(
    to bottom,
    color-mix(in srgb, var(--gas-surface) 88%, transparent) 0%,
    color-mix(in srgb, var(--gas-surface) 55%, transparent) 55%,
    color-mix(in srgb, var(--gas-surface) 0%, transparent) 100%
  );
  -webkit-backdrop-filter: blur(14px) saturate(1.4);
  backdrop-filter: blur(14px) saturate(1.4);
  -webkit-mask-image: linear-gradient(to bottom, #000 0%, #000 50%, transparent 100%);
  mask-image: linear-gradient(to bottom, #000 0%, #000 50%, transparent 100%);
}
.gas-header-side { display: flex; gap: 6px; pointer-events: auto; }
.gas-icon-btn {
  width: 34px; height: 34px;
  border-radius: 999px;
  border: none;
  padding: 0;
  display: inline-flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  color: var(--gas-text);
  background: color-mix(in srgb, var(--gas-surface) 70%, transparent);
  -webkit-backdrop-filter: blur(10px);
  backdrop-filter: blur(10px);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--gas-text) 6%, transparent);
  cursor: pointer;
  transition: background-color 150ms ease, transform 150ms var(--gas-ease), opacity 150ms ease;
}
.gas-icon-btn:hover { background: var(--gas-hover-strong); }
.gas-icon-btn:active { transform: scale(0.9); }
.gas-icon-btn[aria-expanded="true"] { background: var(--gas-hover-strong); }
.gas-header .gas-icon-btn {
  background: var(--gas-bg);
  box-shadow: var(--gas-shadow-sm);
  -webkit-backdrop-filter: none;
  backdrop-filter: none;
}
.gas-header .gas-icon-btn:hover,
.gas-header .gas-icon-btn[aria-expanded="true"] { background: color-mix(in srgb, var(--gas-bg) 90%, var(--gas-text)); }
.gas-icon-btn--plain { background: transparent; box-shadow: none; -webkit-backdrop-filter: none; backdrop-filter: none; }
.gas-icon-btn--plain:hover { background: var(--gas-hover); }
.gas-icon-btn--hidden { visibility: hidden; }

.gas-presence {
  position: absolute;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  pointer-events: auto;
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: calc(100% - 172px);
  min-width: 0;
  padding: 5px 14px 5px 5px;
  border: none;
  border-radius: 22px;
  background: var(--gas-bg);
  color: var(--gas-text);
  font: inherit;
  text-align: left;
  cursor: pointer;
  box-shadow: var(--gas-shadow-sm);
  transition: transform 380ms var(--gas-spring), box-shadow 240ms ease, padding 320ms var(--gas-ease);
  animation: gas-presence-in 420ms var(--gas-spring) 80ms backwards;
}
@keyframes gas-presence-in {
  from { opacity: 0; transform: translateX(-50%) translateY(-8px) scale(0.92); }
  to   { opacity: 1; transform: translateX(-50%) translateY(0) scale(1); }
}
/* Clicked: nudged forward (down + slightly larger) with the description revealed. */
.gas-presence--open {
  transform: translateX(-50%) translateY(4px) scale(1.04);
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.12), var(--gas-edge);
  padding-right: 16px;
}
.gas-presence--brand { padding: 7px 14px; }
.gas-presence-brand { display: block; height: 20px; max-width: 150px; object-fit: contain; }
.gas-avatar { flex-shrink: 0; width: 26px; height: 26px; border-radius: 999px; }
.gas-avatar img { width: 100%; height: 100%; border-radius: inherit; object-fit: cover; display: block; }
.gas-presence-text { display: flex; flex-direction: column; min-width: 0; }
.gas-presence-title {
  font-size: 13.5px;
  font-weight: 650;
  line-height: 1.25;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.gas-presence-sub {
  display: grid;
  grid-template-rows: 0fr;
  opacity: 0;
  transition: grid-template-rows 320ms var(--gas-ease), opacity 220ms ease;
}
.gas-presence--open .gas-presence-sub { grid-template-rows: 1fr; opacity: 1; }
.gas-presence-sub > span {
  overflow: hidden;
  min-height: 0;
  font-size: 12px;
  line-height: 1.35;
  color: var(--gas-muted);
  white-space: nowrap;
  text-overflow: ellipsis;
}

/* ===== Message list ===== */
.gas-scroll {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
  padding: 76px 18px 12px;
  scroll-padding-top: 72px;
  -webkit-mask-image: linear-gradient(to bottom, transparent 0, #000 44px);
  mask-image: linear-gradient(to bottom, transparent 0, #000 44px);
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--gas-text) 22%, transparent) transparent;
  overscroll-behavior: contain;
}
.gas-scroll::-webkit-scrollbar { width: 6px; }
.gas-scroll::-webkit-scrollbar-track { background: transparent; }
.gas-scroll::-webkit-scrollbar-thumb { background: color-mix(in srgb, var(--gas-text) 22%, transparent); border-radius: 999px; }

.gas-row { display: flex; width: 100%; margin-top: 14px; }
.gas-row--tight { margin-top: 4px; }
.gas-row--user { justify-content: flex-end; }
.gas-row--agent { justify-content: flex-start; gap: 10px; }
.gas-row-avatar { width: 24px; height: 24px; border-radius: 999px; flex-shrink: 0; margin-top: 1px; object-fit: cover; }
.gas-row-avatar--spacer { visibility: hidden; }
.gas-row-body { display: flex; flex-direction: column; min-width: 0; max-width: calc(100% - 34px); }
.gas-row-body--wide { flex: 1; }
/* A reply with code uses the full text column so short snippets don't shrink to badges. */
.gas-row-body:has(.gas-code) { flex: 1; }
.gas-agent-text:has(.gas-code) { width: 100%; }
/* Agent text keeps a right gutter (mirroring the visitor bubbles' left gutter) so replies
   read as coming from the left. Full-width cards and forms (--wide) are exempt. */
.gas-row--agent .gas-row-body:not(.gas-row-body--wide) { max-width: calc(100% - 34px - 36px); }
.gas-row--user .gas-row-body { align-items: flex-end; max-width: 82%; }
.gas-row--in.gas-row--user  { animation: gas-in-user 360ms var(--gas-spring) both; }
.gas-row--in.gas-row--agent { animation: gas-in-agent 420ms var(--gas-ease) both; }
@keyframes gas-in-user {
  from { opacity: 0; transform: translateX(14px) translateY(6px) scale(0.96); }
  to   { opacity: 1; transform: none; }
}
@keyframes gas-in-agent {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: none; }
}

.gas-bubble {
  padding: 10px 16px;
  border-radius: 20px;
  background: var(--gas-primary);
  color: var(--gas-on-primary);
  line-height: 1.45;
  word-break: break-word;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
}
.gas-bubble p { margin: 0 0 6px; }
.gas-bubble p:last-child { margin-bottom: 0; }
.gas-row--tight.gas-row--user .gas-bubble { border-top-right-radius: 8px; }
.gas-bubble a { color: inherit; }
.gas-agent-text { color: var(--gas-text); line-height: 1.55; word-break: break-word; overflow-wrap: anywhere; padding-top: 1px; min-width: 0; max-width: 100%; }
/* InteractiveContent renders quick options with white-space: nowrap; let long ones wrap
   (and every block stay inside the column) instead of running off the panel. */
.gas-agent-text button:not(.gas-code-copy) { white-space: normal !important; max-width: 100%; text-align: left; line-height: 1.35; border-radius: 16px !important; padding: 7px 13px !important; box-shadow: none !important; }
/* Each ***option*** is its own block, spaced by InteractiveContent's 12px block gap;
   pull consecutive option blocks together so they read as one group. */
.gas-agent-text > div > div:has(> button) + div:has(> button) { margin-top: -7px; }
/* Suggested ***questions*** look like suggestions, not like the visitor's own (solid
   primary) bubbles: an outlined chip in the primary colour with a reply arrow. Only the
   quick-option buttons (two levels inside the reply) get this; item widgets keep theirs. */
.gas-agent-text > div > div > button:not(.gas-code-copy) {
  display: inline-flex !important;
  align-items: center;
  gap: 5px;
  background: var(--gas-bg) !important;
  color: var(--gas-primary) !important;
  border: none !important;
  box-shadow: none !important;
  font-weight: 550 !important;
  font-size: 13.5px !important;
  padding: 7px 13px 7px 8px !important;
  transition: color 150ms ease !important;
}
.gas-agent-text > div > div > button::before {
  content: '';
  width: 14px; height: 14px;
  flex-shrink: 0;
  background-color: currentColor;
  -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='15 10 20 15 15 20'/%3E%3Cpath d='M4 4v7a4 4 0 0 0 4 4h12'/%3E%3C/svg%3E") no-repeat center / contain;
  mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='15 10 20 15 15 20'/%3E%3Cpath d='M4 4v7a4 4 0 0 0 4 4h12'/%3E%3C/svg%3E") no-repeat center / contain;
  opacity: 0.75;
}
.gas-agent-text > div > div > button:not(.gas-code-copy):hover:not(:disabled) {
  color: color-mix(in srgb, var(--gas-primary) 65%, var(--gas-bg)) !important;
}
.gas-agent-text > div > div > button:active:not(:disabled) { transform: scale(0.98); }
.gas-agent-text img, .gas-agent-text table { max-width: 100%; }

/* ===== Code ===== */
.gas-agent-text :not(pre) > code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace;
  font-size: 0.86em;
  padding: 1px 6px;
  border-radius: 6px;
  background: var(--gas-hover-strong);
}
.gas-code {
  width: 100%;
  margin: 4px 0;
  border-radius: 14px;
  overflow: hidden;
  background: #16181d;
  color: #e6e8eb;
  box-shadow: var(--gas-shadow-sm);
}
.gas-code-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 6px 8px 6px 14px;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
}
.gas-code-lang { font-size: 11.5px; font-weight: 600; letter-spacing: 0.02em; color: #9aa3ad; text-transform: lowercase; }
.gas-code-copy {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 4px 8px;
  border: none; border-radius: 8px;
  background: transparent;
  color: #b8c0c9;
  font-size: 11.5px; font-weight: 600;
  cursor: pointer;
  transition: background-color 120ms ease, color 120ms ease;
}
.gas-code-copy:hover { background: rgba(255, 255, 255, 0.08); color: #fff; }
.gas-code-copy--done { color: #4ade80; }
.gas-code pre {
  margin: 0;
  padding: 12px 14px 14px;
  overflow-x: auto;
  white-space: pre !important;
  overflow-wrap: normal;
  word-break: normal;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace;
  font-size: 12.5px;
  line-height: 1.6;
  tab-size: 2;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.2) transparent;
}
.gas-code pre::-webkit-scrollbar { height: 6px; }
.gas-code pre::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.2); border-radius: 999px; }
.gas-code code { font: inherit; background: none; padding: 0; }
.gas-tok-comment { color: #7d8590; font-style: italic; }
.gas-tok-string { color: #a5d6a7; }
.gas-tok-number { color: #f8a46b; }
.gas-tok-keyword { color: #c4a7f5; }
.gas-tok-function { color: #82aaff; }
.gas-tok-property { color: #7fd8e8; }
.gas-tok-tag { color: #f28b82; }
.gas-agent-text a { color: inherit; text-decoration: underline; text-underline-offset: 2px; }
.gas-agent-text p { margin: 0 0 10px; }
.gas-agent-text p:last-child { margin-bottom: 0; }
/* MarkdownMessage wraps everything in white-space: pre-wrap, which renders the newlines
   *between* blocks as blank lines. Keep line breaks inside paragraphs only. */
.gas-agent-text [style*="pre-wrap"], .gas-bubble [style*="pre-wrap"],
.gas-card-body [style*="pre-wrap"], .gas-hero-body [style*="pre-wrap"] { white-space: normal !important; }
.gas-agent-text p, .gas-bubble p, .gas-card-body p, .gas-hero-body p { white-space: pre-wrap; }
.gas-agent-text ol, .gas-agent-text ul { margin: 4px 0 10px !important; }
.gas-agent-text h1, .gas-agent-text h2, .gas-agent-text h3, .gas-agent-text h4 { font-size: 1.08em; font-weight: 650; line-height: 1.35; margin: 14px 0 6px; }
.gas-agent-text li { margin: 4px 0 !important; }

.gas-receipt {
  display: inline-flex; align-items: center; gap: 3px;
  margin-top: 5px;
  font-size: 11.5px;
  color: var(--gas-muted);
  animation: gas-fade-in 300ms ease both;
}
.gas-receipt--seen { color: var(--gas-primary); }

/* While a reply types out, what is not revealed yet cannot be clicked */
.gas-agent-text--typing { pointer-events: none; }

/* Attachments on a message: pictures for images, file cards for everything else */
.gas-attachments { display: flex; flex-direction: column; gap: 6px; max-width: 100%; }
.gas-attachments--end { align-items: flex-end; }
.gas-attachments--start { align-items: flex-start; }
.gas-attachments--spaced { margin-bottom: 6px; }
.gas-media {
  position: relative;
  display: block;
  overflow: hidden;
  border-radius: 16px;
  background: var(--gas-hover);
  cursor: zoom-in;
  -webkit-tap-highlight-color: transparent;
}
.gas-media img {
  display: block;
  opacity: 0;
  transition: opacity 220ms ease, transform 300ms var(--gas-ease);
}
.gas-media--loaded img { opacity: 1; }
.gas-media:hover img { transform: scale(1.03); }
.gas-media--single { max-width: min(240px, 100%); }
.gas-media--single img { width: auto; height: auto; max-width: 100%; max-height: 300px; min-width: 80px; min-height: 80px; }
.gas-media-grid { display: grid; gap: 4px; max-width: 100%; }
.gas-media-grid--2 { grid-template-columns: repeat(2, 112px); }
.gas-media-grid--3 { grid-template-columns: repeat(3, 82px); }
.gas-media-grid--4 { grid-template-columns: repeat(2, 104px); }
.gas-media-grid--all { grid-template-columns: repeat(3, 82px); }
.gas-media--tile { aspect-ratio: 1; border-radius: 12px; }
.gas-media--tile img { width: 100%; height: 100%; object-fit: cover; }
.gas-media-more {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  background: rgba(15, 23, 42, 0.55);
  color: #fff;
  font-size: 20px; font-weight: 650;
  cursor: pointer;
}
.gas-receipt--failed { color: #dc2626; }
.gas-retry {
  display: inline-flex; align-items: center; gap: 3px;
  padding: 0; border: none; background: none;
  color: inherit; font: inherit; font-weight: 600;
  cursor: pointer;
  transition: opacity 150ms ease;
}
.gas-retry:hover { opacity: 0.7; }

.gas-feedback {
  display: flex; align-items: center; gap: 2px;
  margin-top: 4px; margin-left: -6px;
  height: 26px;
  opacity: 0;
  transition: opacity 160ms ease;
}
.gas-row:hover .gas-feedback, .gas-feedback:focus-within, .gas-feedback--set { opacity: 1; }
.gas-feedback-btn {
  width: 26px; height: 26px;
  border-radius: 8px;
  border: none; background: transparent; padding: 0;
  display: inline-flex; align-items: center; justify-content: center;
  color: var(--gas-muted);
  cursor: pointer;
  transition: background-color 120ms ease, color 120ms ease, transform 120ms ease;
}
.gas-feedback-btn:hover { background: var(--gas-hover); color: var(--gas-text); }
.gas-feedback-btn:active { transform: scale(0.88); }
.gas-feedback-btn--on { color: var(--gas-primary); animation: gas-pop 320ms var(--gas-spring); }
@keyframes gas-pop { 0% { transform: scale(0.7); } 60% { transform: scale(1.15); } 100% { transform: scale(1); } }

.gas-special {
  align-self: center;
  display: inline-flex; align-items: center; gap: 8px;
  margin: 16px auto 4px;
  padding: 7px 14px;
  border-radius: 999px;
  font-size: 12.5px; font-weight: 500;
  background: color-mix(in srgb, var(--gas-primary) 10%, var(--gas-bg));
  color: var(--gas-text);
  animation: gas-fade-in 300ms ease both;
}
.gas-special--warn { background: #fff3e0; color: #b45309; }
.gas-special a { color: inherit; text-decoration: underline; }

/* Time separator + new-message marker */
.gas-time {
  display: flex; align-items: center; gap: 12px;
  margin: 18px 0 2px;
  font-size: 12px;
  color: var(--gas-muted);
  white-space: nowrap;
}
.gas-time::before, .gas-time::after { content: ''; flex: 1; height: 1px; background: color-mix(in srgb, var(--gas-text) 10%, transparent); }
.gas-new-pill {
  align-self: center;
  margin: 16px 0 0;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 12px; font-weight: 600;
  background: var(--gas-primary);
  color: var(--gas-on-primary);
  animation: gas-drop-in 420ms var(--gas-spring) both;
}
@keyframes gas-drop-in {
  from { opacity: 0; transform: translateY(-8px) scale(0.9); }
  to   { opacity: 1; transform: none; }
}

/* Welcome / rich card */
.gas-card {
  background: var(--gas-bg);
  border-radius: 20px;
  padding: 6px;
  box-shadow: var(--gas-shadow-sm);
  /* Fixed to the docked panel's width so expand / fullscreen don't stretch it. */
  width: 100%;
  max-width: 310px;
}
.gas-card-hero {
  background: var(--gas-surface);
  border-radius: 15px;
  padding: 14px 14px 16px;
}
.gas-card-img { display: block; width: 100%; max-height: 160px; object-fit: contain; border-radius: 12px; margin-bottom: 10px; }
.gas-card-title { font-size: 22px; font-weight: 600; line-height: 1.2; color: var(--gas-text); letter-spacing: -0.01em; }
.gas-card-body { margin-top: 6px; font-size: 15px; line-height: 1.45; color: var(--gas-muted); }
.gas-card-body p { margin: 0; }
.gas-chips { display: flex; flex-wrap: wrap; gap: 8px; padding: 10px 6px 6px; }
.gas-chip {
  border: none;
  padding: 8px 14px;
  border-radius: 18px;
  font-size: 13.5px; font-weight: 600;
  background: var(--gas-primary);
  color: var(--gas-on-primary);
  cursor: pointer;
  text-align: left;
  animation: gas-chip-in 380ms var(--gas-spring) both;
  animation-delay: calc(var(--i, 0) * 50ms + 120ms);
  transition: transform 140ms var(--gas-ease), filter 140ms ease, box-shadow 140ms ease;
}
.gas-chip:hover:not(:disabled) { transform: translateY(-1px); filter: brightness(1.08); }
.gas-chip:active:not(:disabled) { transform: scale(0.96); }
.gas-chip:disabled { opacity: 0.55; cursor: default; }
@keyframes gas-chip-in {
  from { opacity: 0; transform: translateY(6px) scale(0.92); }
  to   { opacity: 1; transform: none; }
}

/* Empty state (before the conversation starts) */
.gas-hero {
  margin: auto 0;
  display: flex; flex-direction: column; align-items: center;
  gap: 8px;
  padding: 24px 12px 32px;
  text-align: center;
  animation: gas-fade-up 520ms var(--gas-ease) both;
}
.gas-hero-art { width: 200px; max-width: 70%; height: auto; margin-bottom: 10px; overflow: visible; }
.gas-art-bubble { filter: drop-shadow(0 2px 6px rgba(15, 23, 42, 0.10)); animation: gas-bob 4.8s ease-in-out infinite; transform-box: fill-box; }
.gas-art-bubble--b { animation-delay: -1.6s; }
.gas-art-bubble--c { animation-delay: -3.2s; }
@keyframes gas-bob { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-4px); } }
.gas-art-card { fill: var(--gas-bg); }
.gas-art-primary { fill: var(--gas-primary); }
.gas-art-line { fill: color-mix(in srgb, var(--gas-text) 16%, transparent); }
.gas-art-line-on { fill: color-mix(in srgb, var(--gas-on-primary) 70%, transparent); }
.gas-art-line--soft { opacity: 0.6; }
.gas-art-dot { fill: var(--gas-muted); animation: gas-bounce 1.2s ease-in-out infinite; transform-box: fill-box; }
.gas-art-dot:nth-of-type(2) { animation-delay: 0.15s; }
.gas-art-dot:nth-of-type(3) { animation-delay: 0.3s; }
.gas-hero-title { font-size: 21px; font-weight: 650; letter-spacing: -0.01em; color: var(--gas-text); }
.gas-hero-body { max-width: 280px; font-size: 14.5px; line-height: 1.5; color: var(--gas-muted); }
.gas-hero-body p { margin: 0; }

/* Typing indicator */
/* Same geometry as an agent row (.gas-row--agent + .gas-row-avatar), so the logo stays put
   when the reply replaces the thinking indicator. */
.gas-typing { display: flex; align-items: flex-start; gap: 10px; margin-top: 14px; animation: gas-fade-in 220ms ease both; }
.gas-typing-avatar { width: 24px; height: 24px; border-radius: 999px; flex-shrink: 0; object-fit: cover; margin-top: 1px; }
.gas-typing > .gas-dots, .gas-typing > .gas-thinking { min-height: 24px; margin-top: 1px; display: inline-flex; align-items: center; }
.gas-dots { display: inline-flex; gap: 4px; padding: 6px 2px; }
.gas-dots span {
  width: 6px; height: 6px; border-radius: 999px;
  background: var(--gas-text);
  animation: gas-bounce 1.1s ease-in-out infinite;
}
.gas-dots span:nth-child(2) { animation-delay: 0.15s; }
.gas-dots span:nth-child(3) { animation-delay: 0.3s; }
@keyframes gas-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.45; }
  30% { transform: translateY(-4px); opacity: 1; }
}
.gas-thinking { font-size: 13px; color: var(--gas-muted); animation: gas-think 260ms var(--gas-ease) both; }
@keyframes gas-think { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }

/* Jump to latest */
.gas-jump {
  position: absolute;
  left: 50%;
  z-index: 4;
  transform: translateX(-50%);
  width: 34px; height: 34px;
  border-radius: 999px;
  border: none;
  display: inline-flex; align-items: center; justify-content: center;
  background: var(--gas-bg);
  color: var(--gas-text);
  box-shadow: var(--gas-shadow-md);
  cursor: pointer;
  animation: gas-jump-in 260ms var(--gas-spring) both;
  transition: transform 150ms var(--gas-ease);
}
.gas-jump:hover { transform: translateX(-50%) translateY(-2px); }
/* A reply typing out is laid out whole, so the chat "sees" unread text below it; the view
   follows the typing anyway, so keep the jump button away until it is done. */
.gas-panel:has(.gas-agent-text--typing) .gas-jump { visibility: hidden; pointer-events: none; }
@keyframes gas-jump-in {
  from { opacity: 0; transform: translateX(-50%) translateY(8px) scale(0.8); }
  to   { opacity: 1; transform: translateX(-50%) translateY(0) scale(1); }
}

/* ===== Footer / composer ===== */
.gas-footer { position: relative; z-index: 3; flex-shrink: 0; padding: 6px 12px 10px; }
.gas-composer {
  position: relative;
  display: flex;
  align-items: flex-end;
  gap: 4px;
  padding: 5px;
  border-radius: 26px;
  /* Smooth superellipse corners, between a squircle (2) and a plain round pill (1), where
     supported; other browsers keep the round pill. */
  corner-shape: superellipse(1.4);
  background: var(--gas-input-bg);
  border: 1px solid color-mix(in srgb, var(--gas-border) 90%, transparent);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  transition: border-color 160ms ease, box-shadow 200ms ease;
}
/* Active only while the text field itself has focus: the +, emoji and send buttons (and
   the emoji picker, which lives inside the composer) do not count as using the input. */
.gas-composer:has(.gas-textarea:focus) { border-color: color-mix(in srgb, var(--gas-text) 28%, var(--gas-border)); }
.gas-composer--disabled { opacity: 0.7; }
.gas-textarea {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  resize: none;
  background: transparent;
  color: var(--gas-text);
  font: inherit;
  font-size: var(--gas-fs);
  /* 22px line + 7px padding = 36px, the height of the + and send buttons, so a
     one-line field and its buttons share one centre line. */
  line-height: 22px;
  padding: 7px 8px;
  min-height: 36px;
  max-height: 132px;
  scrollbar-width: none;
}
.gas-textarea::-webkit-scrollbar { width: 0; height: 0; }
.gas-textarea::placeholder { color: var(--gas-muted); opacity: 1; }
.gas-textarea:focus-visible { outline: none; }
.gas-composer .gas-icon-btn { background: var(--gas-hover); box-shadow: none; -webkit-backdrop-filter: none; backdrop-filter: none; width: 36px; height: 36px; }
.gas-composer .gas-icon-btn:hover { background: var(--gas-hover-strong); }
/* Emoji picker: spans the composer, opens upward from the emoji button */
.gas-emoji-btn[aria-expanded="true"] { background: var(--gas-hover-strong) !important; }
.gas-emoji-panel {
  position: absolute;
  z-index: 20;
  left: 0; right: 0;
  bottom: calc(100% + 10px);
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 2px;
  padding: 8px;
  border-radius: 26px;
  corner-shape: superellipse(1.4);
  background: var(--gas-bg);
  box-shadow: var(--gas-shadow-md);
  transform-origin: bottom right;
  animation: gas-pop-in 180ms var(--gas-ease) both;
}
.gas-emoji {
  aspect-ratio: 1;
  display: flex; align-items: center; justify-content: center;
  padding: 0;
  border: none;
  border-radius: 999px;
  background: transparent;
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
  transition: background-color 150ms ease, transform 160ms var(--gas-spring);
}
.gas-emoji:hover { background: var(--gas-hover); transform: scale(1.12); }
.gas-emoji:active { transform: scale(0.92); }
.gas-emoji:focus-visible { outline: none; background: var(--gas-hover-strong); }

/* The shared mic button positions itself 6px inside the pill's border; the send button it
   stands in for sits 5px in (the pill's padding), so line it up with that slot. */
.gas-composer > button[style*="position: absolute"] { right: 5px !important; }
.gas-plus svg { transition: transform 240ms var(--gas-spring); }
.gas-plus[aria-expanded="true"] svg { transform: rotate(45deg); }
.gas-send {
  width: 36px; height: 36px;
  flex-shrink: 0;
  border-radius: 999px;
  border: none; padding: 0;
  display: inline-flex; align-items: center; justify-content: center;
  background: var(--gas-primary);
  color: var(--gas-on-primary);
  cursor: pointer;
  transition: background-color 200ms ease, color 200ms ease, transform 160ms var(--gas-ease);
}
.gas-send:hover:not(:disabled) { transform: translateY(-1px); }
.gas-send:active:not(:disabled) { transform: scale(0.9); }
.gas-send:disabled { background: var(--gas-hover-strong); color: var(--gas-muted); cursor: default; }
.gas-send--fired svg { animation: gas-send-fly 420ms var(--gas-ease); }
@keyframes gas-send-fly {
  0% { transform: translateY(0); opacity: 1; }
  45% { transform: translateY(-14px); opacity: 0; }
  46% { transform: translateY(12px); opacity: 0; }
  100% { transform: translateY(0); opacity: 1; }
}
.gas-start {
  width: 100%;
  height: 46px;
  border: none;
  border-radius: 999px;
  background: var(--gas-primary);
  color: var(--gas-on-primary);
  font-size: 15px; font-weight: 600;
  cursor: pointer;
  transition: transform 160ms var(--gas-ease), filter 160ms ease;
  animation: gas-fade-up 360ms var(--gas-ease) both;
}
.gas-start:hover:not(:disabled) { transform: translateY(-1px); filter: brightness(1.06); }
.gas-start:active:not(:disabled) { transform: scale(0.98); }
.gas-start:disabled { opacity: 0.6; cursor: default; }
.gas-voice-hint { flex: 1; padding: 8px 10px; color: var(--gas-muted); font-size: 14px; align-self: center; }
.gas-meta { padding: 6px 8px 0; text-align: center; font-size: 11.5px; line-height: 1.4; color: var(--gas-muted); }
.gas-meta a { color: inherit; text-decoration: underline; }
.gas-powered { display: inline-flex; align-items: center; gap: 5px; }
.gas-powered svg { color: var(--gas-text); display: block; }
.gas-toast {
  display: flex; align-items: center; gap: 8px;
  margin: 0 4px 8px;
  padding: 10px 14px;
  border-radius: 14px;
  background: #fff3e0; color: #b45309;
  font-size: 13.5px;
  animation: gas-fade-up 280ms var(--gas-ease) both;
}

/* ===== Upload sheet (staged attachments) ===== */
.gas-sheet {
  position: absolute;
  left: 12px; right: 12px;
  bottom: calc(100% - 4px);
  z-index: 8;
  padding: 6px 14px 14px;
  border-radius: 24px;
  background: var(--gas-bg);
  color: var(--gas-text);
  box-shadow: 0 -2px 12px rgba(15, 23, 42, 0.08), var(--gas-edge);
  animation: gas-sheet-in 420ms var(--gas-spring) both;
}
@keyframes gas-sheet-in {
  from { opacity: 0; transform: translateY(24px) scale(0.98); }
  to   { opacity: 1; transform: none; }
}
.gas-sheet-head {
  display: flex; align-items: center; gap: 10px;
  width: 100%;
  padding: 8px 0;
  border: none; background: transparent;
  color: var(--gas-text);
  font-size: 14.5px; font-weight: 600;
  cursor: pointer;
  text-align: left;
}
.gas-sheet-status { flex: 1; }
.gas-sheet-toggle {
  width: 30px; height: 30px;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: 999px;
  transition: transform 300ms var(--gas-ease), background-color 150ms ease;
}
.gas-sheet-head:hover .gas-sheet-toggle { background: var(--gas-hover); }
.gas-sheet--collapsed .gas-sheet-toggle { transform: rotate(180deg); }
.gas-sheet--collapsed { padding-bottom: 6px; }
.gas-sheet-body { display: grid; grid-template-rows: 1fr; transition: grid-template-rows 320ms var(--gas-ease); }
.gas-sheet--collapsed .gas-sheet-body { grid-template-rows: 0fr; }
.gas-sheet-body > div { overflow: hidden; min-height: 0; }
/* Staged files: one row that scrolls sideways, with arrows and a soft fade on a side
   that has more */
.gas-sheet-strip { position: relative; }
.gas-sheet-grid {
  display: flex;
  gap: 10px;
  padding: 6px 0 14px;
  overflow-x: auto;
  overflow-y: hidden;
  scroll-snap-type: x proximity;
  overscroll-behavior-x: contain;
  scrollbar-width: none;
}
.gas-sheet-grid::-webkit-scrollbar { display: none; }
.gas-sheet-grid > * { flex: 0 0 104px; scroll-snap-align: start; }
.gas-sheet-grid--fade-right { -webkit-mask-image: linear-gradient(to right, #000 calc(100% - 36px), transparent); mask-image: linear-gradient(to right, #000 calc(100% - 36px), transparent); }
.gas-sheet-grid--fade-left { -webkit-mask-image: linear-gradient(to left, #000 calc(100% - 36px), transparent); mask-image: linear-gradient(to left, #000 calc(100% - 36px), transparent); }
.gas-sheet-grid--fade-left.gas-sheet-grid--fade-right { -webkit-mask-image: linear-gradient(to right, transparent, #000 36px, #000 calc(100% - 36px), transparent); mask-image: linear-gradient(to right, transparent, #000 36px, #000 calc(100% - 36px), transparent); }
.gas-strip-arrow {
  position: absolute;
  top: calc(6px + 52px);
  z-index: 2;
  width: 32px; height: 32px;
  border-radius: 999px;
  border: none; padding: 0;
  display: inline-flex; align-items: center; justify-content: center;
  background: var(--gas-bg);
  color: var(--gas-text);
  box-shadow: var(--gas-shadow-md);
  cursor: pointer;
  transform: translateY(-50%);
  animation: gas-fade-in 180ms ease both;
  transition: transform 150ms var(--gas-ease);
}
.gas-strip-arrow:hover { transform: translateY(-50%) scale(1.06); }
.gas-strip-arrow:active { transform: translateY(-50%) scale(0.94); }
.gas-strip-arrow--left { left: 2px; }
.gas-strip-arrow--right { right: 2px; }
.gas-tile { display: flex; flex-direction: column; gap: 6px; min-width: 0; animation: gas-chip-in 380ms var(--gas-spring) both; animation-delay: calc(var(--i, 0) * 50ms); }
.gas-tile-thumb {
  position: relative;
  aspect-ratio: 1;
  border-radius: 14px;
  overflow: hidden;
  background: var(--gas-surface);
  display: flex; align-items: center; justify-content: center;
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--gas-text) 8%, transparent);
}
.gas-tile-thumb img { width: 100%; height: 100%; object-fit: cover; display: block; transition: filter 300ms ease, opacity 300ms ease; }
.gas-tile-thumb--busy img { filter: blur(1px) saturate(0.6); opacity: 0.6; }
.gas-tile-icon { display: inline-flex; transform: scale(1.3); }
/* A document tile: same square as an image tile, preview on top and a type + name bar at the bottom */
.gas-tile--doc .gas-tile-thumb {
  flex-direction: column; align-items: stretch; justify-content: flex-start;
  border-radius: 18px; corner-shape: superellipse(1.4);
  background: var(--gas-bg);
}
.gas-tile--doc .gas-doc-thumb { flex: 1; height: auto; min-height: 0; }
.gas-tile--doc .gas-doc-foot { border-top: 1px solid color-mix(in srgb, var(--gas-text) 8%, transparent); padding: 6px 7px; gap: 6px; }
.gas-tile--doc .gas-doc-name { font-size: 11.5px; }
.gas-tile--doc .gas-doc-badge svg { width: 15px; height: 15px; }
.gas-tile--doc .gas-doc-badge-ext { font-size: 6.5px; }
.gas-tile--doc .gas-tile-spinner { top: calc(50% - 30px); }
.gas-tile-thumb--busy .gas-doc-thumb { filter: blur(1px) saturate(0.6); opacity: 0.6; }

/* Documents: a preview (PDF first page, text, or a typed cover) in a squircle card */
.gas-doc {
  display: flex; flex-direction: column;
  width: 224px; max-width: 100%;
  overflow: hidden;
  border-radius: 20px;
  corner-shape: superellipse(1.4);
  background: var(--gas-bg);
  color: var(--gas-text);
  text-decoration: none;
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--gas-text) 10%, transparent), var(--gas-shadow-sm);
  transition: transform 180ms var(--gas-ease), box-shadow 180ms ease;
}
.gas-doc:hover { transform: translateY(-1px); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--gas-text) 14%, transparent), var(--gas-shadow-md); }
.gas-doc:active { transform: scale(0.98); }
.gas-doc-thumb { position: relative; height: 132px; overflow: hidden; background: #fff; }
.gas-doc .gas-doc-thumb { border-bottom: 1px solid color-mix(in srgb, var(--gas-text) 8%, transparent); }
.gas-doc-frame {
  position: absolute; top: 0; left: 0;
  width: 200%; height: 200%;
  transform: scale(0.5); transform-origin: 0 0;
  border: 0;
  pointer-events: none;
  opacity: 0;
  transition: opacity 260ms ease;
}
.gas-doc-frame--ready { opacity: 1; }
.gas-doc-text {
  margin: 0; height: 100%;
  padding: 10px 12px;
  overflow: hidden;
  font: 9.5px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  color: #374151;
  white-space: pre-wrap; word-break: break-word;
  -webkit-mask-image: linear-gradient(#000 70%, transparent);
  mask-image: linear-gradient(#000 70%, transparent);
}
.gas-doc-cover {
  position: absolute; inset: 0;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px;
  background: color-mix(in srgb, var(--doc-color) 9%, var(--gas-bg));
}
.gas-doc-cover--loading { background: var(--gas-hover); animation: gas-doc-pulse 1.2s ease-in-out infinite; }
@keyframes gas-doc-pulse { 50% { opacity: 0.55; } }
.gas-doc-ext { font-size: 11px; font-weight: 700; letter-spacing: 0.06em; color: var(--doc-color); }
.gas-doc-foot { display: flex; align-items: center; gap: 9px; padding: 10px 12px; min-width: 0; }
.gas-doc-badge { display: inline-flex; flex-direction: column; align-items: center; flex-shrink: 0; line-height: 1; }
.gas-doc-badge-ext { margin-top: 1px; font-size: 7.5px; font-weight: 800; letter-spacing: 0.04em; }
.gas-doc-info { display: flex; flex-direction: column; min-width: 0; }
.gas-doc-name { font-size: 13.5px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.gas-doc-meta { font-size: 11.5px; color: var(--gas-muted); }
.gas-tile-spinner { position: absolute; }
.gas-tile-x {
  position: absolute;
  top: 5px; right: 5px;
  width: 22px; height: 22px;
  border-radius: 999px;
  border: none; padding: 0;
  display: inline-flex; align-items: center; justify-content: center;
  background: rgba(15, 23, 42, 0.7);
  color: #fff;
  cursor: pointer;
  opacity: 0;
  transform: scale(0.8);
  transition: opacity 150ms ease, transform 150ms var(--gas-ease);
}
.gas-tile:hover .gas-tile-x, .gas-tile-x:focus-visible { opacity: 1; transform: none; }
@media (hover: none) { .gas-tile-x { opacity: 1; transform: none; } }
.gas-tile-name { font-size: 12.5px; color: var(--gas-text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.gas-tile-add {
  aspect-ratio: 1;
  border-radius: 14px;
  border: 2px dashed color-mix(in srgb, var(--gas-text) 45%, transparent);
  background: transparent;
  color: var(--gas-text);
  display: inline-flex; align-items: center; justify-content: center;
  cursor: pointer;
  transition: background-color 150ms ease, border-color 150ms ease, transform 150ms var(--gas-ease);
}
.gas-tile-add:hover { background: var(--gas-hover); border-color: var(--gas-text); }
.gas-tile-add:active { transform: scale(0.95); }
.gas-sheet-send { width: 100%; height: 42px; background: var(--gas-text); color: var(--gas-bg); }
.gas-sheet-send:hover:not(:disabled) { filter: brightness(1.15); }
.gas-sheet-spinner {
  width: 20px; height: 20px;
  flex-shrink: 0;
  border-radius: 999px;
  border: 2.5px solid color-mix(in srgb, var(--gas-primary) 22%, transparent);
  border-top-color: var(--gas-primary);
  animation: gas-spin 800ms linear infinite;
}
@keyframes gas-spin { to { transform: rotate(360deg); } }
.gas-sheet-check { flex-shrink: 0; }
.gas-sheet-check circle { fill: #16a34a; transform-origin: center; animation: gas-pop 360ms var(--gas-spring) both; }
.gas-sheet-check path {
  fill: none; stroke: #fff; stroke-width: 2.4; stroke-linecap: round; stroke-linejoin: round;
  stroke-dasharray: 16; stroke-dashoffset: 16;
  animation: gas-draw 320ms 180ms var(--gas-ease) forwards;
}
@keyframes gas-draw { to { stroke-dashoffset: 0; } }

/* ===== Popovers (overflow menu, + menu) ===== */
.gas-popover {
  position: absolute;
  z-index: 20;
  min-width: 220px;
  padding: 6px;
  border-radius: 18px;
  background: var(--gas-bg);
  color: var(--gas-text);
  box-shadow: var(--gas-shadow-md);
  transform-origin: var(--gas-origin, top right);
  animation: gas-pop-in 180ms var(--gas-ease) both;
}
@keyframes gas-pop-in {
  from { opacity: 0; transform: scale(0.9) translateY(-4px); }
  to   { opacity: 1; transform: none; }
}
.gas-menu-item {
  display: flex; align-items: center; gap: 12px;
  width: 100%;
  padding: 10px 12px;
  border: none; border-radius: 12px;
  background: transparent;
  color: var(--gas-text);
  font-size: 14px;
  text-align: left;
  cursor: pointer;
  transition: background-color 120ms ease;
}
.gas-menu-item:hover, .gas-menu-item:focus-visible { background: var(--gas-hover); outline: none; }
.gas-menu-item > svg:first-child { color: var(--gas-muted); flex-shrink: 0; }
.gas-menu-item-label { flex: 1; }
.gas-menu-chevron { color: var(--gas-muted); transition: transform 220ms var(--gas-ease); }
.gas-menu-chevron--open { transform: rotate(180deg); }
.gas-menu-sep { height: 1px; margin: 4px 8px; background: color-mix(in srgb, var(--gas-text) 8%, transparent); }
.gas-submenu {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 260ms var(--gas-ease);
}
.gas-submenu--open { grid-template-rows: 1fr; }
.gas-submenu > div { overflow: hidden; min-height: 0; }
.gas-lang {
  display: flex; align-items: center; justify-content: space-between;
  width: 100%;
  padding: 8px 12px 8px 40px;
  border: none; border-radius: 10px;
  background: transparent;
  color: var(--gas-text);
  font-size: 13.5px;
  cursor: pointer;
}
.gas-lang:hover { background: var(--gas-hover); }
.gas-lang--active { font-weight: 600; }
.gas-lang svg { color: var(--gas-primary); }

/* ===== Dialog (reset) ===== */
.gas-overlay {
  position: absolute; inset: 0;
  z-index: 40;
  display: flex; align-items: center; justify-content: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.32);
  -webkit-backdrop-filter: blur(3px);
  backdrop-filter: blur(3px);
  animation: gas-fade-in 180ms ease both;
}
.gas-dialog {
  width: 100%;
  max-width: 320px;
  padding: 22px;
  border-radius: 22px;
  background: var(--gas-bg);
  color: var(--gas-text);
  box-shadow: var(--gas-shadow-lg);
  animation: gas-dialog-in 300ms var(--gas-spring) both;
}
@keyframes gas-dialog-in {
  from { opacity: 0; transform: translateY(10px) scale(0.94); }
  to   { opacity: 1; transform: none; }
}
.gas-dialog h3 { margin: 0; font-size: 17px; font-weight: 650; }
.gas-dialog p { margin: 8px 0 0; font-size: 14px; line-height: 1.5; color: var(--gas-muted); }
.gas-dialog-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 20px; }
.gas-btn {
  height: 38px;
  padding: 0 18px;
  border: none;
  border-radius: 999px;
  font-size: 14px; font-weight: 600;
  cursor: pointer;
  transition: background-color 150ms ease, transform 150ms var(--gas-ease), filter 150ms ease;
}
.gas-btn:active { transform: scale(0.96); }
.gas-btn--ghost { background: var(--gas-hover); color: var(--gas-text); }
.gas-btn--ghost:hover { background: var(--gas-hover-strong); }
.gas-btn--danger { background: #dc2626; color: #fff; }
.gas-btn--danger:hover { background: #b91c1c; }
.gas-btn--primary { background: var(--gas-primary); color: var(--gas-on-primary); }
.gas-btn--primary:hover:not(:disabled) { filter: brightness(1.07); }
.gas-btn--primary:disabled { opacity: 0.5; cursor: default; }

/* Full-panel HITL form */
.gas-form-overlay {
  position: absolute; inset: 0;
  z-index: 30;
  display: flex; flex-direction: column;
  background: var(--gas-bg);
  animation: gas-fade-up 300ms var(--gas-ease) both;
}

/* ===== Launcher + teaser (closed state) ===== */
.gas-launcher {
  width: 58px; height: 58px;
  border-radius: 999px;
  border: none; padding: 0;
  display: inline-flex; align-items: center; justify-content: center;
  background: var(--gas-primary);
  color: var(--gas-on-primary);
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.18);
  animation: gas-launcher-in 420ms var(--gas-spring) both;
  transition: transform 220ms var(--gas-spring), box-shadow 220ms ease;
}
.gas-launcher:hover { transform: translateY(-2px) scale(1.05); }
.gas-launcher:active { transform: scale(0.93); }
.gas-launcher svg { transition: transform 300ms var(--gas-spring); }
.gas-launcher:hover svg { transform: rotate(-12deg) scale(1.08); }
@keyframes gas-launcher-in {
  from { opacity: 0; transform: scale(0.4) rotate(-30deg); }
  to   { opacity: 1; transform: none; }
}
.gas-launcher-badge {
  position: absolute;
  top: -3px; right: -3px;
  min-width: 21px; height: 21px;
  padding: 0 6px;
  border-radius: 999px;
  background: #ef4444;
  color: #fff;
  font-size: 11.5px; font-weight: 700; line-height: 21px;
  text-align: center;
  box-shadow: 0 0 0 2px var(--gas-bg);
  animation: gas-pop 420ms var(--gas-spring) both;
}

.gas-teaser {
  display: flex; flex-direction: column; gap: 10px;
  font-family: var(--gas-font);
  color: var(--gas-text);
  transform-origin: var(--gas-origin, bottom right);
  animation: gas-teaser-in 520ms var(--gas-spring) 120ms both;
}
@keyframes gas-teaser-in {
  from { opacity: 0; transform: translateY(14px) scale(0.92); }
  to   { opacity: 1; transform: none; }
}
.gas-teaser-top { display: flex; align-items: center; justify-content: space-between; }
.gas-teaser-pill {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 5px 14px 5px 5px;
  border: none; border-radius: 999px;
  background: var(--gas-bg);
  color: var(--gas-text);
  font-size: 13.5px; font-weight: 600;
  box-shadow: var(--gas-shadow-sm);
  cursor: pointer;
  transition: transform 160ms var(--gas-ease);
}
.gas-teaser-pill:hover { transform: translateY(-1px); }
.gas-teaser-pill img { width: 26px; height: 26px; border-radius: 999px; object-fit: cover; }
.gas-teaser-pill img.gas-teaser-brand { width: auto; height: 20px; border-radius: 0; margin-left: 8px; }
.gas-teaser-close { width: 30px; height: 30px; background: color-mix(in srgb, var(--gas-bg) 85%, transparent); box-shadow: var(--gas-shadow-sm); }
.gas-teaser-card {
  padding: 6px;
  border-radius: 24px;
  background: var(--gas-bg);
  box-shadow: var(--gas-shadow-lg), var(--gas-edge);
}
.gas-teaser-hero {
  display: flex; flex-direction: column; gap: 4px;
  width: 100%;
  padding: 14px 16px 16px;
  border: none; border-radius: 18px;
  background: var(--gas-surface);
  color: var(--gas-text);
  text-align: left;
  cursor: pointer;
  transition: filter 150ms ease;
}
.gas-teaser-hero:hover { filter: brightness(0.98); }
.gas-teaser-title { font-size: 22px; font-weight: 600; letter-spacing: -0.01em; line-height: 1.2; }
.gas-teaser-body { font-size: 15px; line-height: 1.4; color: var(--gas-muted); }
.gas-teaser-body p { margin: 0; }
.gas-teaser-body [style*="pre-wrap"] { white-space: normal !important; }
.gas-teaser-chips { padding: 10px 6px 4px; }
.gas-teaser-preview { padding: 12px 14px; animation: gas-fade-up 360ms var(--gas-ease) both; }
.gas-teaser-preview .gas-teaser-body {
  color: var(--gas-text);
  font-size: 14px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.gas-teaser-input {
  display: flex; align-items: center; gap: 6px;
  margin-top: 4px;
  padding: 4px 4px 4px 14px;
}
.gas-teaser-input input {
  flex: 1; min-width: 0;
  border: none; outline: none;
  background: transparent;
  color: var(--gas-text);
  font: inherit; font-size: 14.5px;
  padding: 8px 0;
}
.gas-teaser-input input::placeholder { color: var(--gas-muted); }
@media (max-width: 768px) { .gas-teaser-input input { font-size: 16px; } }

@keyframes gas-fade-in { from { opacity: 0; } to { opacity: 1; } }
@keyframes gas-fade-up { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }

@media (max-width: 768px) {
  .gas-textarea { font-size: 16px; }
}
@media (prefers-reduced-motion: reduce) {
  .gas-root *, .gas-root *::before, .gas-root *::after {
    animation-duration: 1ms !important;
    animation-delay: 0ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 1ms !important;
  }
}
`;
