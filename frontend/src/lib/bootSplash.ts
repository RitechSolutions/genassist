/**
 * Controls the animated logo splash that lives in index.html (#app-splash).
 *
 * The splash paints with the HTML, before the JS bundle arrives. React then
 * keeps it on screen for as long as any <AppLoader /> is mounted (registration
 * check, permission load, feature-flag hydration...) and fades it into the app
 * once nothing is holding it. Later loads (e.g. right after login) re-show the
 * same splash, replaying the intro, but only when they take longer than
 * SHOW_DELAY_MS so quick ones never flash.
 */

/** Cold start: keep the splash until the logo has finished forming. */
const MIN_BOOT_MS = 1200;
/** Later loads shorter than this never show the splash. */
const SHOW_DELAY_MS = 200;
/** Once re-shown, stay up at least this long so it doesn't blink. */
const MIN_SHOW_MS = 900;
/** Grace period for one loader handing over to the next across renders. */
const HANDOFF_MS = 120;
/** Matches the #app-splash opacity transition in index.html. */
const FADE_MS = 400;

type Phase = "visible" | "hiding" | "hidden";

let phase: Phase = "visible";
let holds = 0;
let appMounted = false;
/** performance.now() when the splash last became visible; 0 = the boot splash. */
let shownAt = 0;
let showTimer: ReturnType<typeof setTimeout> | undefined;
let hideTimer: ReturnType<typeof setTimeout> | undefined;

const splash = (): HTMLElement | null =>
  typeof document === "undefined" ? null : document.getElementById("app-splash");

const svgOf = (node: HTMLElement) => node.querySelector("svg");

const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false);

function clearTimer(timer: ReturnType<typeof setTimeout> | undefined) {
  if (timer !== undefined) clearTimeout(timer);
}

/** Rewind every CSS and SMIL animation to the start of the intro. */
function restartAnimation(node: HTMLElement) {
  node.classList.remove("gas-play");
  void node.offsetWidth; // force a reflow so the CSS animations restart
  node.classList.add("gas-play");
  const svg = svgOf(node);
  if (!svg) return;
  if (prefersReducedMotion()) {
    svg.setCurrentTime(1.6);
    svg.pauseAnimations();
  } else {
    svg.setCurrentTime(0);
    svg.unpauseAnimations();
  }
}

function show() {
  showTimer = undefined;
  const node = splash();
  if (!node || holds === 0) return;
  clearTimer(hideTimer);
  hideTimer = undefined;

  if (phase === "hidden") {
    node.classList.add("gas-out");
    node.hidden = false;
    restartAnimation(node);
    void node.offsetWidth;
  }
  node.classList.remove("gas-out");
  phase = "visible";
  shownAt = performance.now();
}

function hide() {
  hideTimer = undefined;
  const node = splash();
  if (!node || holds > 0 || phase !== "visible") return;
  phase = "hiding";
  node.classList.add("gas-out");
  hideTimer = setTimeout(() => {
    hideTimer = undefined;
    node.hidden = true;
    svgOf(node)?.pauseAnimations();
    phase = "hidden";
  }, FADE_MS);
}

function scheduleHide() {
  if (!appMounted || holds > 0 || phase !== "visible") return;
  clearTimer(hideTimer);
  const minUntil = shownAt === 0 ? MIN_BOOT_MS : shownAt + MIN_SHOW_MS;
  const wait = Math.max(HANDOFF_MS, minUntil - performance.now());
  hideTimer = setTimeout(hide, wait);
}

/**
 * Keep the splash on screen until the returned release function is called.
 * Safe to call any number of times; each release only counts once.
 */
export function holdSplash(): () => void {
  holds += 1;

  if (phase === "visible") {
    clearTimer(hideTimer);
    hideTimer = undefined;
  } else if (phase === "hiding") {
    // Still fading out: bring it straight back instead of blinking.
    show();
  } else if (showTimer === undefined) {
    showTimer = setTimeout(show, SHOW_DELAY_MS);
  }

  let released = false;
  return () => {
    if (released) return;
    released = true;
    holds -= 1;
    if (holds > 0) return;
    clearTimer(showTimer);
    showTimer = undefined;
    scheduleHide();
  };
}

/** Called once the React tree has committed; lets the boot splash go. */
export function markAppMounted() {
  if (appMounted) return;
  appMounted = true;
  const node = splash();
  if (!node) {
    phase = "hidden";
    return;
  }
  if (prefersReducedMotion()) {
    // Backup for the inline script in index.html.
    svgOf(node)?.setCurrentTime(1.6);
    svgOf(node)?.pauseAnimations();
  }
  scheduleHide();
}
