/**
 * "Add screenshot": the browser's own screen-share picker (Chrome's Tab / Window / Entire
 * Screen dialog, Firefox's and Safari's equivalents), one frame grabbed from the chosen
 * surface, returned as a PNG file ready for the normal upload flow.
 *
 * Needs the Screen Capture API, which desktop browsers have in secure contexts (https or
 * localhost); mobile browsers don't, so the action is hidden there. When the widget runs
 * inside an iframe, the iframe also needs `allow="display-capture"`.
 */

/** Screenshots wider than this are scaled down (keeps 4K/5K captures a sensible size). */
export const MAX_SCREENSHOT_WIDTH = 2560;

/** Whether this browser can take a screenshot (Screen Capture API available). */
export function canCaptureScreen(): boolean {
  return (
    typeof navigator !== 'undefined' &&
    typeof navigator.mediaDevices?.getDisplayMedia === 'function'
  );
}

/** Whether the host's allowed file types (empty = all) let a PNG screenshot through. */
export function screenshotAllowed(allowed: readonly string[]): boolean {
  return allowed.length === 0 || allowed.includes('image/*') || allowed.includes('image/png');
}

/** `screenshot-2026-11-25-153012.png` */
export function screenshotFileName(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `screenshot-${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}-${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}.png`;
}

/** A capture's size scaled down to at most `maxWidth` wide, keeping its aspect ratio. */
export function fitWidth(width: number, height: number, maxWidth: number = MAX_SCREENSHOT_WIDTH): { width: number; height: number } {
  if (width <= maxWidth) return { width, height };
  return { width: maxWidth, height: Math.round((height * maxWidth) / width) };
}

/** The user closed the picker or refused sharing: not an error to report. */
export function isCaptureCancelled(error: unknown): boolean {
  const name = (error as { name?: string } | null)?.name;
  return name === 'NotAllowedError' || name === 'AbortError';
}

/** Waits until the video has a real frame to draw (the first one can be blank). */
function firstFrame(video: HTMLVideoElement): Promise<void> {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('No frame from the shared screen')), 5000);
    const done = () => {
      clearTimeout(timeout);
      resolve();
    };
    const v = video as HTMLVideoElement & { requestVideoFrameCallback?: (cb: () => void) => number };
    if (typeof v.requestVideoFrameCallback === 'function') {
      v.requestVideoFrameCallback(() => done());
    } else {
      video.addEventListener('loadeddata', () => setTimeout(done, 150), { once: true });
    }
  });
}

/**
 * Opens the browser's share picker and returns one frame of the chosen tab, window or
 * screen as a PNG file. Resolves to null when the user cancels the picker; rejects on a
 * real failure. Sharing stops right after the frame is taken.
 */
export async function captureScreenshot(now: Date = new Date()): Promise<File | null> {
  let stream: MediaStream;
  try {
    stream = await navigator.mediaDevices.getDisplayMedia({
      video: { displaySurface: 'browser' } as MediaTrackConstraints, // offer tabs first, where supported
      audio: false,
      // Chrome hints, ignored elsewhere: let the visitor pick this very tab (the page they
      // need help with) and don't offer switching surfaces mid-share.
      selfBrowserSurface: 'include',
      surfaceSwitching: 'exclude',
    } as DisplayMediaStreamOptions);
  } catch (error) {
    if (isCaptureCancelled(error)) return null;
    throw error;
  }

  const video = document.createElement('video');
  try {
    video.muted = true;
    video.playsInline = true;
    video.srcObject = stream;
    await video.play();
    await firstFrame(video);

    const { width, height } = fitWidth(video.videoWidth, video.videoHeight);
    if (!width || !height) throw new Error('The shared screen has no size');
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('Canvas is not available');
    ctx.drawImage(video, 0, 0, width, height);

    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/png'));
    if (!blob) throw new Error('Could not encode the screenshot');
    return new File([blob], screenshotFileName(now), { type: 'image/png', lastModified: now.getTime() });
  } finally {
    stream.getTracks().forEach((track) => track.stop());
    video.srcObject = null;
  }
}
