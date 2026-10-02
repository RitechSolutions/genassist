import React, { useEffect, useRef, useState } from "react";
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/hover-card";

interface RevealProps {
  /** Names the field, in the trigger's label and as the card heading */
  label: string;
  value: string;
  /** Follows the value in both places, for a truncation marker */
  suffix?: string;
  /** Layout and text styling for the trigger */
  className: string;
  /** Clipping goes here, not on the trigger: a button forces its own inner display */
  clip: string;
}

/** Shows a value in full, on hover or on focus, but only while the clip hides some of it */
export const Reveal: React.FC<RevealProps> = ({
  label,
  value,
  suffix,
  className,
  clip,
}) => {
  const box = useRef<HTMLSpanElement>(null);
  const [boundary, setBoundary] = useState<Element | null>(null);
  const [clipped, setClipped] = useState(false);

  useEffect(() => {
    const outer = box.current;
    if (!outer) return;
    setBoundary(outer.closest('[role="dialog"]'));
    const measure = () => {
      const inner = outer.querySelector("[data-clip]");
      if (inner)
        setClipped(
          inner.scrollHeight > inner.clientHeight + 1 ||
            inner.scrollWidth > inner.clientWidth + 1,
        );
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(outer);
    return () => observer.disconnect();
  }, [value]);

  const text = (
    <>
      {value}
      {suffix && <span className="text-muted-foreground">{suffix}</span>}
    </>
  );
  const body = (
    <span data-clip className={clip}>
      {text}
    </span>
  );
  return (
    <span ref={box} className={className}>
      {clipped && value.trim() ? (
        <HoverCard>
          <HoverCardTrigger asChild>
            <button
              type="button"
              aria-label={`Show full ${label}`}
              className="block w-full cursor-text text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1"
            >
              {body}
            </button>
          </HoverCardTrigger>
          <HoverCardContent
            align="end"
            collisionBoundary={boundary}
            collisionPadding={8}
            className="w-80 max-h-64 overflow-y-auto"
          >
            <div className="space-y-2">
              <p className="text-sm font-medium">{label}</p>
              <p className="text-xs whitespace-pre-wrap break-words">{text}</p>
            </div>
          </HoverCardContent>
        </HoverCard>
      ) : (
        body
      )}
    </span>
  );
};
