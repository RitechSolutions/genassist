import React, { useCallback, useEffect, useRef } from "react";

import { cn } from "@/helpers/utils";

// Tiles touch edge to edge (no gap); their rounded corners leave only the tiny diamond between four of them.
const TILE_PX = 28;
const GAP_PX = 0;
// How long a tile stays lit after the pointer leaves it; neighbours fade sooner.
const LIT_MS = 1100;
const NEIGHBOUR_MS = 700;
// A few tiles twinkle on their own so the surface never looks dead.
const TWINKLE_EVERY_MS = 420;

const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * A field of small rounded squares that light up in the brand blue under the
 * pointer and fade back out, with a slow random twinkle while idle. Purely
 * decorative: it fills whatever box it is given and ignores clicks.
 */
export const HoverGrid: React.FC<{ className?: string }> = ({ className }) => {
  const hostRef = useRef<HTMLDivElement>(null);
  const tilesRef = useRef<HTMLSpanElement[]>([]);
  const columnsRef = useRef(0);
  const timersRef = useRef<Map<HTMLSpanElement, ReturnType<typeof setTimeout>>>(new Map());

  const light = useCallback((tile: HTMLSpanElement | undefined, level: "hot" | "warm" | "faint", ms: number) => {
    if (!tile) return;
    const timers = timersRef.current;
    const pending = timers.get(tile);
    if (pending) clearTimeout(pending);
    tile.dataset.lit = level;
    timers.set(
      tile,
      setTimeout(() => {
        delete tile.dataset.lit;
        timers.delete(tile);
      }, ms)
    );
  }, []);

  // Build the tiles to fill the host; rebuild when it is resized.
  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const build = () => {
      // One tile more than fits on each side, centred, so the field runs off both edges
      // instead of leaving a margin where a whole tile would not fit.
      const columns = Math.ceil((host.clientWidth + GAP_PX) / (TILE_PX + GAP_PX)) + 2;
      const rows = Math.max(1, Math.ceil((host.clientHeight + GAP_PX) / (TILE_PX + GAP_PX)));
      columnsRef.current = columns;
      host.replaceChildren();
      tilesRef.current = [];
      for (let i = 0; i < columns * rows; i += 1) {
        const tile = document.createElement("span");
        tile.className = "hover-grid-tile";
        host.appendChild(tile);
        tilesRef.current.push(tile);
      }
      host.style.gridTemplateColumns = `repeat(${columns}, ${TILE_PX}px)`;
    };
    build();
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(build) : null;
    observer?.observe(host);
    return () => observer?.disconnect();
  }, []);

  // Idle twinkle.
  useEffect(() => {
    if (prefersReducedMotion()) return;
    const timer = setInterval(() => {
      const tiles = tilesRef.current;
      if (tiles.length === 0) return;
      light(tiles[Math.floor(Math.random() * tiles.length)], "faint", LIT_MS * 2);
    }, TWINKLE_EVERY_MS);
    return () => clearInterval(timer);
  }, [light]);

  useEffect(() => {
    const timers = timersRef.current;
    return () => timers.forEach((timer) => clearTimeout(timer));
  }, []);

  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const host = hostRef.current;
    if (!host) return;
    const rect = host.getBoundingClientRect();
    const columns = columnsRef.current;
    // The grid is wider than the host and centred, so it starts a little left of the edge.
    const gridWidth = columns * (TILE_PX + GAP_PX) - GAP_PX;
    const offsetX = (rect.width - gridWidth) / 2;
    const column = Math.floor((event.clientX - rect.left - offsetX) / (TILE_PX + GAP_PX));
    const row = Math.floor((event.clientY - rect.top) / (TILE_PX + GAP_PX));
    if (column < 0 || column >= columns || row < 0) return;
    const tiles = tilesRef.current;
    const index = row * columns + column;
    light(tiles[index], "hot", LIT_MS);
    // A soft halo: the four neighbours, each with a small chance so the trail looks organic.
    const neighbours = [index - 1, index + 1, index - columns, index + columns];
    neighbours.forEach((n, i) => {
      const sameRow = i < 2 ? Math.floor(n / columns) === row : true;
      if (n >= 0 && n < tiles.length && sameRow && Math.random() < 0.55) light(tiles[n], "warm", NEIGHBOUR_MS);
    });
  };

  return (
    <div
      ref={hostRef}
      aria-hidden
      onPointerMove={onPointerMove}
      className={cn("hover-grid grid content-start justify-center overflow-hidden", className)}
      style={{ gap: GAP_PX, "--hover-grid-tile": `${TILE_PX}px` } as React.CSSProperties}
    />
  );
};
