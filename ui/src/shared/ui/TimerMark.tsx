import type { CSSProperties } from "react";

import { timerHue, timerLayers } from "./timerMarks";

export interface TimerMarkProps {
  /** The event's icon, as the schedule names it. */
  icon: string;
  /** "md" for the lists, "sm" for the collapsed plaque, "lg" for the panel's leading card. */
  size?: "sm" | "md" | "lg";
  className?: string;
}

/**
 * An event's mark on a disc of its kind's hue, the same in the panel and on the plaque. It stands
 * beside the event's name, which says the same thing, so it is hidden from assistive technology.
 */
export default function TimerMark({ icon, size = "md", className = "" }: TimerMarkProps) {
  // the hue is data, so it travels in a custom property and base.css does the painting
  const style: CSSProperties = { "--tmark-hue": timerHue(icon) };
  return (
    <span className={`ui-tmark ui-tmark-${size} ${className}`} style={style} aria-hidden="true">
      <svg viewBox="0 0 24 24" focusable="false">
        {timerLayers(icon).map((layer, i) => (
          <path
            // the layers of one mark never change order: the index is the layer's identity
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
    </span>
  );
}
