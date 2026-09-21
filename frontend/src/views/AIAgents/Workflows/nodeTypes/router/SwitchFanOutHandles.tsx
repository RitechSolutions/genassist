import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  Handle,
  Position,
  ReactFlowState,
  useStore,
  useUpdateNodeInternals,
} from "reactflow";
import { NodeHandler } from "../../types/nodes";
import { HandleTooltip } from "../../components/custom/HandleTooltip";
import { getHandlerPosition } from "../../utils/helpers";
import { computeSwitchFanOut, FanOutShape, FanOutSize } from "./switchHandleLayout";

const BRAND = "hsl(var(--brand-600))";
const BRAND_SOFT = "hsl(var(--brand-600) / 0.35)";
const BRAND_HALO = "hsl(var(--brand-600) / 0.07)";

const OPEN_DELAY_MS = 90;
const CLOSE_DELAY_MS = 160;
const EXPAND_MS = 280;
const COLLAPSE_MS = 180;
const MAX_TOTAL_STAGGER_MS = 260;
const EASE_OUT = "cubic-bezier(0.22, 1, 0.36, 1)";

const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

interface SwitchFanOutHandlesProps {
  nodeId: string;
  handlers: NodeHandler[];
  /** "arc" around the compact tile, "bracket" along the detailed card's edge. */
  shape: FanOutShape;
}

/**
 * Output handles for a Switch with more outputs than fit on the node's edge.
 *
 * Collapsed, the outputs are bundled under a count badge on the node's right
 * edge. Hovering the node fans them out around it with a label per case, so
 * every case can be seen and connected; edges follow the handles while they
 * move. The fan stays open while a connection is being dragged from the node.
 *
 * Renders inside the box the handles anchor to (the compact tile, or the
 * detailed card's node) and sizes itself from it.
 */
const SwitchFanOutHandles: React.FC<SwitchFanOutHandlesProps> = ({
  nodeId,
  handlers,
  shape,
}) => {
  const rootRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState<FanOutSize>({ width: 0, height: 0 });
  const updateNodeInternals = useUpdateNodeInternals();
  const [hovered, setHovered] = useState(false);
  const [activeHandleId, setActiveHandleId] = useState<string | null>(null);

  const isConnectingFromNode = useStore(
    (s: ReactFlowState) => s.connectionNodeId === nodeId
  );
  // Stable string so the node only re-renders when its own connections change.
  const connectedKey = useStore((s: ReactFlowState) =>
    s.edges
      .filter((edge) => edge.source === nodeId && edge.sourceHandle)
      .map((edge) => edge.sourceHandle)
      .sort()
      .join("|")
  );
  const connected = useMemo(
    () => new Set(connectedKey ? connectedKey.split("|") : []),
    [connectedKey]
  );

  const targets = handlers.filter((h) => h.type === "target");
  const outputs = handlers.filter((h) => h.type === "source");
  const layout = useMemo(
    () => computeSwitchFanOut(outputs.length, size, shape),
    [outputs.length, size, shape]
  );

  // Track the anchoring box (the detailed card changes height with its content).
  // offsetWidth/Height are layout sizes, unaffected by the canvas zoom.
  useLayoutEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const measure = () =>
      setSize((prev) =>
        prev.width === root.offsetWidth && prev.height === root.offsetHeight
          ? prev
          : { width: root.offsetWidth, height: root.offsetHeight }
      );
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(root);
    return () => observer.disconnect();
  }, []);

  const expanded = hovered || isConnectingFromNode;
  const reducedMotion = prefersReducedMotion();
  const stagger = Math.min(22, MAX_TOTAL_STAGGER_MS / Math.max(1, outputs.length));
  const settleMs = reducedMotion
    ? 0
    : expanded
    ? EXPAND_MS + stagger * outputs.length + 60
    : COLLAPSE_MS + 60;

  // Hover anywhere on the node (tile, name, toolbar, or the open fan itself).
  useEffect(() => {
    const nodeElement = rootRef.current?.closest<HTMLElement>(".react-flow__node");
    if (!nodeElement) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const schedule = (next: boolean, delay: number) => {
      clearTimeout(timer);
      timer = setTimeout(() => setHovered(next), delay);
    };
    const onEnter = () => schedule(true, OPEN_DELAY_MS);
    const onLeave = () => schedule(false, CLOSE_DELAY_MS);
    nodeElement.addEventListener("mouseenter", onEnter);
    nodeElement.addEventListener("mouseleave", onLeave);
    return () => {
      clearTimeout(timer);
      nodeElement.removeEventListener("mouseenter", onEnter);
      nodeElement.removeEventListener("mouseleave", onLeave);
    };
  }, []);

  // Lift the node above its neighbours while the fan is open.
  useEffect(() => {
    const nodeElement = rootRef.current?.closest<HTMLElement>(".react-flow__node");
    if (!nodeElement || !expanded) return;
    const previous = nodeElement.style.zIndex;
    nodeElement.style.zIndex = "1000";
    return () => {
      nodeElement.style.zIndex = previous;
    };
  }, [expanded]);

  // React Flow measures handle positions on demand; re-measure every frame
  // while the handles animate so connected edges travel with them.
  useEffect(() => {
    let frame = 0;
    const until = performance.now() + settleMs;
    const tick = () => {
      updateNodeInternals(nodeId);
      if (performance.now() < until) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [expanded, outputs.length, size, nodeId, settleMs, updateNodeInternals]);

  useEffect(() => {
    if (!expanded) setActiveHandleId(null);
  }, [expanded]);

  const duration = (ms: number) => (reducedMotion ? 0 : ms);
  const { hitArea } = layout;

  return (
    <div ref={rootRef} className="absolute inset-0">
      {targets.map((handler, index) => (
        <HandleTooltip
          key={handler.id}
          type={handler.type}
          position={handler.position as Position}
          id={handler.id}
          nodeId={nodeId}
          compatibility={handler.compatibility}
          label={handler.label}
          style={{ top: getHandlerPosition(index, targets.length) }}
        />
      ))}

      {/* Keeps the hover alive in the gap between the node and the fan. */}
      <div
        aria-hidden
        className="nodrag absolute"
        style={{
          left: hitArea.left,
          top: hitArea.top,
          width: hitArea.width,
          height: hitArea.height,
          borderRadius: hitArea.borderRadius,
          transformOrigin: `${layout.anchor.x - hitArea.left}px ${layout.anchor.y - hitArea.top}px`,
          zIndex: -1,
          pointerEvents: expanded ? "auto" : "none",
          background: `radial-gradient(closest-side, ${BRAND_HALO}, ${BRAND_HALO} 55%, transparent)`,
          opacity: expanded ? 1 : 0,
          transform: `scale(${expanded ? 1 : 0.6})`,
          transition: `opacity ${duration(expanded ? EXPAND_MS : COLLAPSE_MS)}ms ease, transform ${duration(
            expanded ? EXPAND_MS : COLLAPSE_MS
          )}ms ${EASE_OUT}`,
        }}
      />

      {outputs.map((handler, index) => {
        const point = layout.points[index];
        const dx = expanded ? point.x - layout.anchor.x : 0;
        const dy = expanded ? point.y - layout.anchor.y : 0;
        const delay = expanded && !reducedMotion ? index * stagger : 0;
        const isActive = activeHandleId === handler.id;
        const isConnected = connected.has(handler.id);
        const dimmed = activeHandleId !== null && !isActive;
        const label = handler.label || handler.id.replace(/^output_/, "");

        return (
          <Handle
            key={handler.id}
            id={handler.id}
            type="source"
            position={Position.Right}
            onMouseEnter={() => setActiveHandleId(handler.id)}
            onMouseLeave={() =>
              setActiveHandleId((current) => (current === handler.id ? null : current))
            }
            style={{
              left: layout.anchor.x,
              top: layout.anchor.y,
              right: "auto",
              bottom: "auto",
              width: "calc(var(--handler-diameter) * 1px)",
              height: "calc(var(--handler-diameter) * 1px)",
              minWidth: 0,
              background: "transparent",
              border: "none",
              zIndex: isActive ? 2 : 1,
              pointerEvents: expanded ? "all" : "none",
              transform: `translate(-50%, -50%) translate(${dx}px, ${dy}px)`,
              transition: `transform ${duration(expanded ? EXPAND_MS : COLLAPSE_MS)}ms ${EASE_OUT} ${delay}ms`,
            }}
          >
            {/* Pulse behind the handle under the cursor. */}
            {isActive && (
              <span
                className="pointer-events-none absolute inset-0 animate-ping rounded-full"
                style={{ background: BRAND_SOFT }}
              />
            )}
            {/* The visible dot; scaled on its own so React Flow still measures
                the handle at its real size. Hollow while nothing is connected. */}
            <span
              className="pointer-events-none absolute inset-0 rounded-full"
              style={{
                background: isConnected ? BRAND : "hsl(var(--card))",
                border: `2px solid ${BRAND}`,
                opacity: expanded ? 1 : 0,
                transform: `scale(${isActive ? 1.45 : 1})`,
                transition: `transform 150ms ${EASE_OUT}, opacity ${duration(120)}ms ease ${delay}ms`,
              }}
            />
            {/* Case label, sitting just above the edge it names. It belongs to
                the handle, so hovering it highlights the case and dragging from
                it starts a connection. */}
            <span
              className="absolute cursor-crosshair whitespace-nowrap rounded-md border px-1.5 py-px text-[11px] font-medium leading-4 shadow-sm"
              title={label}
              style={{
                left: "calc(100% + 6px)",
                bottom: "calc(50% + 3px)",
                maxWidth: 150,
                overflow: "hidden",
                textOverflow: "ellipsis",
                background: isActive ? BRAND : "hsl(var(--card))",
                borderColor: isActive ? BRAND : "hsl(var(--border))",
                color: isActive ? "white" : "hsl(var(--foreground))",
                pointerEvents: expanded ? "auto" : "none",
                opacity: expanded ? (dimmed ? 0.55 : 1) : 0,
                transform: `translateX(${expanded ? (isActive ? 2 : 0) : -6}px)`,
                transition: expanded
                  ? `opacity ${duration(180)}ms ease ${reducedMotion ? 0 : delay + 110}ms, transform ${duration(
                      220
                    )}ms ${EASE_OUT} ${isActive || dimmed ? 0 : reducedMotion ? 0 : delay + 110}ms, background-color 150ms ease, color 150ms ease, border-color 150ms ease`
                  : `opacity ${duration(90)}ms ease, transform ${duration(90)}ms ease`,
              }}
            >
              {label}
            </span>
          </Handle>
        );
      })}

      {/* Collapsed: one badge carrying the number of bundled outputs. */}
      <div
        aria-hidden
        className="pointer-events-none absolute flex h-6 min-w-6 items-center justify-center rounded-full px-1.5 text-[11px] font-semibold text-white shadow-md ring-2 ring-background"
        style={{
          left: layout.anchor.x,
          top: layout.anchor.y,
          background: BRAND,
          zIndex: 3,
          opacity: expanded ? 0 : 1,
          transform: `translate(-50%, -50%) scale(${expanded ? 0.4 : 1})`,
          transition: `opacity ${duration(expanded ? 120 : 200)}ms ease ${
            expanded || reducedMotion ? 0 : 80
          }ms, transform ${duration(expanded ? 160 : 240)}ms ${EASE_OUT} ${
            expanded || reducedMotion ? 0 : 80
          }ms`,
        }}
      >
        {outputs.length}
      </div>
    </div>
  );
};

export default SwitchFanOutHandles;
