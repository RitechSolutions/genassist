import { useEffect, useState } from "react";
import { Bot, Flag, Play } from "lucide-react";

interface WorkflowLoadingOverlayProps {
  visible: boolean;
}

const FADE_OUT_MS = 300;

const TILES = [
  { Icon: Play, delay: "0s" },
  { Icon: Bot, delay: "0.7s" },
  { Icon: Flag, delay: "1.4s" },
];
const CONNECTOR_DELAYS = ["0.3s", "1s"];

/**
 * Covers the canvas while a workflow is fetched and its nodes are mounted: a
 * tiny workflow that "runs" in a loop. The animation (see `.wf-loader-*` in
 * index.css) uses only transform/opacity so it keeps moving on the compositor
 * while the main thread is busy rendering a large graph.
 */
export const WorkflowLoadingOverlay: React.FC<WorkflowLoadingOverlayProps> = ({
  visible,
}) => {
  // Stay mounted through the fade-out, then unmount.
  const [mounted, setMounted] = useState(visible);
  useEffect(() => {
    if (visible) {
      setMounted(true);
      return;
    }
    const timer = setTimeout(() => setMounted(false), FADE_OUT_MS);
    return () => clearTimeout(timer);
  }, [visible]);

  if (!mounted) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className={`absolute inset-0 z-20 flex flex-col items-center justify-center gap-8 bg-muted transition-opacity duration-300 ${
        visible ? "opacity-100" : "pointer-events-none opacity-0"
      }`}
    >
      <div className="flex items-center" aria-hidden="true">
        {TILES.map(({ Icon, delay }, index) => (
          <div key={delay} className="flex items-center">
            <div
              className="wf-loader-node flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-600 text-white shadow-lg"
              style={{ animationDelay: delay }}
            >
              <Icon className="h-6 w-6" />
            </div>
            {index < TILES.length - 1 && (
              <div className="relative mx-2 w-12">
                <div className="border-t-2 border-dashed border-brand-600/40" />
                <span
                  className="wf-loader-dot absolute -top-1 left-0 h-2.5 w-2.5 rounded-full bg-brand-600"
                  style={{ animationDelay: CONNECTOR_DELAYS[index] }}
                />
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="text-center">
        <div className="text-base font-semibold text-foreground">
          Loading workflow
        </div>
      </div>
    </div>
  );
};
