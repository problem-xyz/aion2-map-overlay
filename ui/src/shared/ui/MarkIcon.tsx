import { iconLayers, type MarkIconName } from "./markIcons";

/**
 * One of the map's marks as an SVG, the same drawing the map stamps from a bitmap: an object's
 * icon in the objects list, beside a route point in the editor, a quest star on the steps plaque.
 * Decoration beside a name or a number that says the same, so it is hidden from assistive
 * technology.
 */
export default function MarkIcon({ name, className }: { name: MarkIconName; className: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      {iconLayers(name).map((layer, i) => (
        <path
          // the layers of one icon never change order: the index is the layer's identity
          key={i}
          d={layer.d}
          fill={layer.fill ?? "none"}
          stroke={layer.stroke}
          strokeWidth={layer.width}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      ))}
    </svg>
  );
}
