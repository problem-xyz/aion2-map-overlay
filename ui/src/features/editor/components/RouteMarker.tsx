import L, { type LeafletEventHandlerFnMap, type Marker as LeafletMarker } from "leaflet";
import { memo, useEffect, useMemo, useRef } from "react";
import { Marker } from "react-leaflet";

import { useEditorActions } from "../EditorContext";
import { toLatLng, toPoint } from "../lib/crs";
import type { Point } from "../lib/geometry";
import type { EditorMarker } from "../lib/routeDoc";

export interface RouteMarkerProps {
  marker: EditorMarker;
  number: number;
  /** How many earlier points stand on the same spot: this one is drawn that many places aside. */
  stack: number;
  /** Away from the selected point: faded, as the legs there are. */
  isFar: boolean;
  color: string;
  isLast: boolean;
  isSelected: boolean;
}

const SIZE = 24;
// Where points overlap, the one earlier in the route is on top, as its leg is on the canvas.
// Leaflet orders markers by their y on screen plus zIndexOffset: a marker's size per point
// outweighs any y two overlapping markers can differ by, and the selection the longest route.
const Z_PER_POINT = SIZE;
const SELECTED_Z = 100_000;

/** The label goes into an HTML string: whatever the user typed must stay text. */
function escapeAttr(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/** Position of the marker being dragged: Leaflet declares the event's `target` as any. */
function draggedTo(target: unknown): Point {
  return toPoint((target as LeafletMarker).getLatLng());
}

/**
 * `memo` is not decoration here: dragging rebuilds the marker array on every frame, but the
 * markers themselves stay the same objects, so only the one under the cursor re-renders. The icon
 * is memoized together with the marker — it used to go into a module-level Map, which grew with
 * every new combination of number, color and selection and was never cleared.
 */
function RouteMarker({
  marker,
  number,
  stack,
  isFar,
  color,
  isLast,
  isSelected,
}: RouteMarkerProps) {
  const actions = useEditorActions();

  const icon = useMemo(() => {
    const cls = ["mo-marker", isLast ? "last" : "", isSelected ? "selected" : ""]
      .filter(Boolean)
      .join(" ");
    // The map shows only the number; hovering a marker names what it is for
    const title = marker.text ? ` title="${escapeAttr(marker.text)}"` : "";
    return L.divIcon({
      className: "mo-marker-host",
      html: `<div class="${cls}" style="--mo-color:${color}"${title}>${number}</div>`,
      iconSize: [SIZE, SIZE],
      iconAnchor: [SIZE / 2, SIZE / 2],
    });
  }, [number, color, isLast, isSelected, marker.text]);

  // The stack and the fading are set on the element, not made part of the icon: dragging a point
  // off a spot it shares changes its stack on the first frame, and a new icon mid-drag ends the
  // drag (see the handlers below)
  const ref = useRef<LeafletMarker | null>(null);
  useEffect(() => {
    const el = ref.current?.getElement();
    if (!el) return;
    el.style.setProperty("--mo-stack", String(stack));
    el.classList.toggle("far", isFar);
  }, [stack, isFar, icon]);

  const handlers = useMemo<LeafletEventHandlerFnMap>(
    () => ({
      // Shift: the route comes back here -- a click alone lands on this point and selects it
      click: (e) => {
        if (e.originalEvent.shiftKey) actions.repeatMarker(marker.id);
        else actions.select(marker.id);
      },
      // Selection happens on dragend, not on dragstart. Changing the selection changes the icon
      // and zIndexOffset, and on setIcon/setZIndexOffset Leaflet rebuilds its Draggable and snaps
      // the marker back to the position from the model — dragging an unselected marker died after
      // the very first frame, dragend never fired, and nothing reached the undo history.
      dragstart: () => actions.beginEdit(),
      drag: (e) => actions.moveMarker(marker.id, draggedTo(e.target)),
      dragend: (e) => {
        actions.select(marker.id);
        actions.endEdit(marker.id, draggedTo(e.target));
      },
    }),
    [actions, marker.id],
  );

  return (
    <Marker
      ref={ref}
      position={toLatLng(marker.x, marker.y)}
      draggable
      keyboard={false}
      icon={icon}
      zIndexOffset={isSelected ? SELECTED_Z : -number * Z_PER_POINT}
      eventHandlers={handlers}
    />
  );
}

export default memo(RouteMarker);
