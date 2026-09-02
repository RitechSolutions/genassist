import { cn } from "@/lib/utils";

const MOCKUP_LIGHT_SRC = "/mockup-light.png";
const MOCKUP_DARK_SRC = "/mockup-dark.png";

interface AuthMockupPanelProps {
  /** Optional class name to override styles (e.g. background). Default background is #F4F4F5 (light) / the app background token (dark). */
  className?: string;
}

/**
 * Right-hand dashboard preview shown on the Login/Signup pages. Renders a
 * theme-specific mockup: the light image under the default theme and the dark
 * image when `.dark` is on <html>. The swap is pure CSS (`dark:` variants) so it
 * happens before paint with no flash. The image is anchored top-left and cover-
 * sized so the sidebar + dashboard header stay visible while the panel fills.
 */
export function AuthMockupPanel({ className }: AuthMockupPanelProps) {
  return (
    <div
      role="img"
      aria-label="Dashboard preview"
      className={cn(
        "relative hidden min-h-full overflow-hidden bg-[#F4F4F5] md:block dark:bg-background",
        className
      )}
    >
      {/* Light theme */}
      <div
        aria-hidden
        style={{ backgroundImage: `url('${MOCKUP_LIGHT_SRC}')` }}
        className="absolute inset-0 bg-cover bg-left-top bg-no-repeat dark:hidden"
      />
      {/* Dark theme */}
      <div
        aria-hidden
        style={{ backgroundImage: `url('${MOCKUP_DARK_SRC}')` }}
        className="absolute inset-0 hidden bg-cover bg-left-top bg-no-repeat dark:block"
      />
    </div>
  );
}
