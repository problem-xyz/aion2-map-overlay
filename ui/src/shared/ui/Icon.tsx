/**
 * The interface's icons: one set, drawn here, on a 16px grid with a 1.5px stroke in
 * `currentColor`.
 *
 * Inline SVG rather than a library: the set is small, the design stage adds no dependencies,
 * and a glyph from the font (the pencil, the cross, the tick) used to render in whatever face
 * Windows picked for it, at a weight that matched nothing beside it. An icon is decoration
 * here: it is always `aria-hidden`, and the control it sits in carries the name
 * (`IconButton`'s `label`, or the button's own text).
 *
 * The stroke is 1.5 beside regular text and reads the same next to the 600-weight labels of the
 * small buttons; `strong` gives 2 for the few icons that stand alone at a small size.
 */

import type { ReactNode } from "react";

export type IconName =
  | "edit"
  | "close"
  | "closeGlint"
  | "trash"
  | "check"
  | "pin"
  | "pinOn"
  | "undo"
  | "redo"
  | "copy"
  | "paste"
  | "export"
  | "import"
  | "folder"
  | "plus"
  | "play"
  | "stop"
  | "keyboard"
  | "chevron"
  | "chevronLeft"
  | "chevronDown"
  | "route"
  | "flag"
  | "list"
  | "gear"
  | "eye"
  | "eyeOff"
  | "record"
  | "area"
  | "map"
  | "clock"
  | "timeline"
  | "painting"
  | "bell"
  | "share"
  | "layers"
  | "search"
  | "grip"
  | "target"
  | "up"
  | "down"
  | "minus"
  | "fit"
  | "info"
  | "external";

const PATHS: Record<IconName, ReactNode> = {
  // Drawn as the client draws its glyphs, not in outline: solid and cut into facets, the
  // lower-right side of the body and the cone a shade back, as if lit from the top left. The
  // lead, the cone, the body and the eraser are four pieces with a hairline between them.
  edit: (
    <g stroke="none" fill="currentColor">
      <path d="M2.2 13.8L2.82 12.16L3.84 13.18ZM2.98 11.75L3.72 9.1L5.31 10.69L3.61 12.39ZM4.22 8.6L9.02 3.79L10.61 5.39L5.81 10.19ZM9.52 3.3L10.72 2.1L11.82 2.34L13.66 4.18L13.9 5.28L12.7 6.48Z" />
      <path
        d="M3.61 12.39L5.31 10.69L6.9 12.28L4.25 13.02ZM5.81 10.19L10.61 5.39L12.21 6.98L7.4 11.78Z"
        fillOpacity=".55"
      />
    </g>
  ),
  close: <path d="M4 4l8 8M12 4l-8 8" />,
  // The client's own close cross: two blades, broad at the crossing and needle-thin at the tips
  closeGlint: (
    <path
      d="M2 2L8.8 7.2 14 14 7.2 8.8ZM14 2 8.8 8.8 2 14 7.2 7.2Z"
      fill="currentColor"
      stroke="none"
    />
  ),
  // Solid, as the pencil: a handle, a lid pointed at both ends, and a tapering bin with three
  // slots cut through it. Its right half is a shade back, the same light as the pencil's.
  trash: (
    <g stroke="none" fill="currentColor">
      <path d="M6.1 1.5h3.8l.55 1.25h-4.9z" />
      <path d="M1.75 4.1L3 3.25h10l1.25.85L13 5H3z" />
      <path
        d="M3.4 6h4.6v8.75H5.1a.9.9 0 0 1-.9-.8zM5.35 7.6v5.4h1.1V7.6zM7.45 7.6v5.4H8V7.6z"
        fillRule="evenodd"
      />
      {/* The middle slot is cut half from each side of the join, or evenodd would fill the
          half of it that lies outside this path's own outline. */}
      <path
        d="M8 6h4.6l-.8 7.95a.9.9 0 0 1-.9.8H8zM8 7.6v5.4h.55V7.6zM9.55 7.6v5.4h1.1V7.6z"
        fillRule="evenodd"
        fillOpacity=".55"
      />
    </g>
  ),
  check: <path d="M3 8.5l3.25 3L13 4.5" />,
  // A pushpin: the cap, the body narrowing under it, the flared rim, the needle. Filled, it is
  // pinned: the outline is the state that is off, the fill the one that is on.
  pin: (
    <>
      <path d="M6 1.75h4a.75.75 0 0 1 0 1.5h-.4l.55 4.6c1.6.45 2.6 1.3 2.6 2.15H3.25c0-.85 1-1.7 2.6-2.15l.55-4.6H6a.75.75 0 0 1 0-1.5z" />
      <path d="M8 10v4.25" />
    </>
  ),
  pinOn: (
    <>
      <path
        d="M6 1.75h4a.75.75 0 0 1 0 1.5h-.4l.55 4.6c1.6.45 2.6 1.3 2.6 2.15H3.25c0-.85 1-1.7 2.6-2.15l.55-4.6H6a.75.75 0 0 1 0-1.5z"
        fill="currentColor"
      />
      <path d="M8 10v4.25" />
    </>
  ),
  undo: (
    <>
      <path d="M5.5 3.5L2.5 6.5l3 3" />
      <path d="M2.5 6.5h7a3.5 3.5 0 010 7H6" />
    </>
  ),
  redo: (
    <>
      <path d="M10.5 3.5l3 3-3 3" />
      <path d="M13.5 6.5h-7a3.5 3.5 0 000 7H10" />
    </>
  ),
  copy: (
    <>
      <rect x="5.5" y="5.5" width="8" height="8" rx="1" />
      <path d="M10.5 5.5v-2a1 1 0 00-1-1h-6a1 1 0 00-1 1v6a1 1 0 001 1h2" />
    </>
  ),
  paste: (
    <>
      <path d="M5.5 3H4a1 1 0 00-1 1v9a1 1 0 001 1h8a1 1 0 001-1V4a1 1 0 00-1-1h-1.5" />
      <rect x="5.5" y="1.75" width="5" height="2.5" rx=".75" />
    </>
  ),
  export: (
    <>
      <path d="M8 10V2.5M5 5.5l3-3 3 3" />
      <path d="M2.5 10v2.5a1 1 0 001 1h9a1 1 0 001-1V10" />
    </>
  ),
  import: (
    <>
      <path d="M8 2.5V10M5 7l3 3 3-3" />
      <path d="M2.5 10v2.5a1 1 0 001 1h9a1 1 0 001-1V10" />
    </>
  ),
  folder: <path d="M2 4.5a1 1 0 011-1h3l1.5 1.5H13a1 1 0 011 1v6.5a1 1 0 01-1 1H3a1 1 0 01-1-1z" />,
  plus: <path d="M8 3v10M3 8h10" />,
  play: <path d="M5 3.5v9l7.5-4.5z" fill="currentColor" />,
  stop: <rect x="4" y="4" width="8" height="8" rx="1" fill="currentColor" />,
  keyboard: (
    <>
      <rect x="1.5" y="4" width="13" height="8.5" rx="1.25" />
      <path d="M4 7h1M7 7h1M10 7h2M4 9.75h8" />
    </>
  ),
  chevron: <path d="M6 3.5L10.5 8 6 12.5" />,
  chevronLeft: <path d="M10 3.5L5.5 8 10 12.5" />,
  chevronDown: <path d="M4 6l4 4 4-4" />,
  route: (
    <>
      <circle cx="4" cy="12" r="1.8" />
      <circle cx="12" cy="4" r="1.8" />
      <path d="M5.5 11C9 10 7 6 10.5 5" />
    </>
  ),
  flag: <path d="M3.5 14V2.5M3.5 3h8l-1.5 3 1.5 3h-8" />,
  list: (
    <>
      <path d="M6 4h7.5M6 8h7.5M6 12h7.5" />
      <circle cx="3" cy="4" r=".8" />
      <circle cx="3" cy="8" r=".8" />
      <circle cx="3" cy="12" r=".8" />
    </>
  ),
  // A cog with six square teeth round a hub: the rays it had read as a sun
  gear: (
    <>
      <path d="M6.34 3.18L6.54 1.15A7 7 0 0 1 9.46 1.15L9.66 3.18A5.1 5.1 0 0 1 11.35 4.15L13.2 3.32A7 7 0 0 1 14.66 5.84L13.01 7.03A5.1 5.1 0 0 1 13.01 8.97L14.66 10.16A7 7 0 0 1 13.2 12.68L11.35 11.85A5.1 5.1 0 0 1 9.66 12.82L9.46 14.85A7 7 0 0 1 6.54 14.85L6.34 12.82A5.1 5.1 0 0 1 4.65 11.85L2.8 12.68A7 7 0 0 1 1.34 10.16L2.99 8.97A5.1 5.1 0 0 1 2.99 7.03L1.34 5.84A7 7 0 0 1 2.8 3.32L4.65 4.15A5.1 5.1 0 0 1 6.34 3.18Z" />
      <circle cx="8" cy="8" r="2.2" />
    </>
  ),
  eye: (
    <>
      <path d="M1.5 8S4 3.5 8 3.5 14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8z" />
      <circle cx="8" cy="8" r="2" />
    </>
  ),
  eyeOff: (
    <>
      <path d="M1.5 8S4 3.5 8 3.5c1.1 0 2.1.3 3 .8M14.5 8S12 12.5 8 12.5c-1.1 0-2.1-.3-3-.8" />
      <path d="M2.5 13.5l11-11" />
    </>
  ),
  record: (
    <>
      <rect x="1.5" y="4" width="9.5" height="8" rx="1" />
      <path d="M11 7l3.5-2v6L11 9" />
    </>
  ),
  area: <path d="M2 5V2.5h2.5M11.5 2.5H14V5M14 11v2.5h-2.5M4.5 13.5H2V11" />,
  map: <path d="M1.5 3.5l4-1.5 5 2 4-1.5v10l-4 1.5-5-2-4 1.5zM5.5 2v10M10.5 4v10" />,
  // a bell: a reminder about to sound
  bell: <path d="M4 11.5V7.5a4 4 0 0 1 8 0v4l1 1.5H3zM6.5 14.5a1.5 1.5 0 0 0 3 0" />,
  // a stopwatch: the timers
  clock: (
    <>
      <circle cx="8" cy="9" r="5.5" />
      <path d="M8 6v3l2 1.5M6.5 1.5h3M8 1.5v2" />
    </>
  ),
  share: (
    <>
      <circle cx="11.5" cy="3.5" r="1.75" />
      <circle cx="4.5" cy="8" r="1.75" />
      <circle cx="11.5" cy="12.5" r="1.75" />
      <path d="M6 7l4-2.5M6 9l4 2.5" />
    </>
  ),
  // lanes of bars and the line at now: the day timeline
  timeline: <path d="M2 4.5h5M6 8h7M3 11.5h6M10.5 2v12" />,
  // a framed picture: a world boss that drops a painting
  painting: (
    <>
      <rect x="2.5" y="3" width="11" height="10" rx="1" />
      <path d="M4.5 11l2.5-3 2 2 1.5-1.5 1.5 2.5" />
      <circle cx="10.5" cy="6" r="0.9" />
    </>
  ),
  layers: <path d="M8 2l6 3.5-6 3.5-6-3.5zM2 9l6 3.5L14 9" />,
  search: (
    <>
      <circle cx="7" cy="7" r="4.5" />
      <path d="M10.5 10.5L14 14" />
    </>
  ),
  grip: (
    <>
      <circle cx="6" cy="4" r=".9" fill="currentColor" stroke="none" />
      <circle cx="10" cy="4" r=".9" fill="currentColor" stroke="none" />
      <circle cx="6" cy="8" r=".9" fill="currentColor" stroke="none" />
      <circle cx="10" cy="8" r=".9" fill="currentColor" stroke="none" />
      <circle cx="6" cy="12" r=".9" fill="currentColor" stroke="none" />
      <circle cx="10" cy="12" r=".9" fill="currentColor" stroke="none" />
    </>
  ),
  target: (
    <>
      <circle cx="8" cy="8" r="5.5" />
      <circle cx="8" cy="8" r="1.5" />
    </>
  ),
  up: <path d="M4 10l4-4 4 4" />,
  down: <path d="M4 6l4 4 4-4" />,
  minus: <path d="M3 8h10" />,
  fit: <path d="M2 5V2.5h2.5M11.5 2.5H14V5M14 11v2.5h-2.5M4.5 13.5H2V11" />,
  info: (
    <>
      <circle cx="8" cy="8" r="6.25" />
      <path d="M8 7.25v4M8 4.75v.01" />
    </>
  ),
  // A page that opens in the browser, outside the app: an arrow leaving its box
  external: (
    <>
      <path d="M9.5 2.5h4v4M13.5 2.5l-6 6" />
      <path d="M11.5 9.5v3a1 1 0 01-1 1h-7a1 1 0 01-1-1v-7a1 1 0 011-1h3" />
    </>
  ),
};

export interface IconProps {
  name: IconName;
  /** A 2px stroke, for an icon that stands alone at a small size. */
  strong?: boolean;
  className?: string;
}

export default function Icon({ name, strong = false, className }: IconProps) {
  return (
    <svg
      className={className ? `ui-icon ${className}` : "ui-icon"}
      viewBox="0 0 16 16"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth={strong ? 2 : 1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {PATHS[name]}
    </svg>
  );
}
