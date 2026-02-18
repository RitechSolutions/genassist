import { cn } from "@/lib/utils";

const MOCKUP_IMAGE_SRC = "/mockup.png";

interface AuthMockupPanelProps {
  /** Optional class name to override styles (e.g. background). Default background is #F4F4F5. */
  className?: string;
}

export function AuthMockupPanel({ className }: AuthMockupPanelProps) {
  return (
    <div
      role="img"
      aria-label="Dashboard preview"
      style={{
        backgroundImage: `url('${MOCKUP_IMAGE_SRC}')`,
        backgroundPosition: "right bottom",
      }}
      className={cn(
        "hidden md:block bg-contain bg-no-repeat min-h-full bg-[#F4F4F5]",
        className
      )}
    />
  );
}
