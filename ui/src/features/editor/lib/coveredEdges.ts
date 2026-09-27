import type L from "leaflet";

/**
 * How much of the map the floating panels cover, as Leaflet padding: the dock on the left, the
 * inspector on the right, the keys strip at the foot. Read off the page, since the drawers open
 * and close and their widths follow the window.
 */
export function coveredEdges(map: L.Map): { topLeft: L.PointTuple; bottomRight: L.PointTuple } {
  const box = map.getContainer().getBoundingClientRect();
  const gap = 24;
  const right = (selector: string) => {
    const el = document.querySelector(selector);
    return el ? el.getBoundingClientRect().right - box.left : 0;
  };
  const left = (selector: string) => {
    const el = document.querySelector(selector);
    return el ? box.right - el.getBoundingClientRect().left : 0;
  };
  const dock = Math.max(right(".ed-drawer"), right(".ed-rail"));
  const inspector = Math.max(left(".ed-inspector"), left(".ed-zoom"));
  const strip = document.querySelector(".ed-keys");
  const bottom = strip ? box.bottom - strip.getBoundingClientRect().top : 0;
  return { topLeft: [dock + gap, gap], bottomRight: [inspector + gap, bottom + gap] };
}
