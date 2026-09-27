import { useId, type CSSProperties, type ReactNode } from "react";

import InfoTip from "./InfoTip";

// The share left of the knob travels in a CSS variable, which CSSProperties does not know about
interface FillStyle extends CSSProperties {
  "--fill": string;
}

export interface SliderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  format?: ((value: number) => string) | null;
  hint?: ReactNode;
  /** The longer explanation, behind an "i" beside the label. */
  tip?: ReactNode;
  onChange: (value: number) => void;
}

/**
 * A range with a readout.
 *
 * The readout is deliberately outside the label: while it was inside, the accessible name was
 * the two glued together ("Opacity70%"), it changed on every drag step, and the value was
 * announced twice. The formatted value belongs in aria-valuetext instead -- "120 px of map" is
 * what the setting means, 0.003 is only what the control carries.
 */
export default function Slider({
  label,
  value,
  min,
  max,
  step,
  format = null,
  hint = null,
  tip = null,
  onChange,
}: SliderProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const text = format ? format(value) : String(value);
  // the track is painted up to the knob from this, as the client fills its sliders
  const share = max > min ? Math.min(1, Math.max(0, (value - min) / (max - min))) : 0;
  const fill: FillStyle = { "--fill": `${(share * 100).toFixed(2)}%` };
  return (
    <div className="ui-field">
      <div className="ui-field-head">
        <span className="ui-field-title">
          <label htmlFor={id} className="ui-field-label">
            {label}
          </label>
          {tip ? <InfoTip topic={label}>{tip}</InfoTip> : null}
        </span>
        <span className="ui-field-value">{text}</span>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        style={fill}
        // Without a formatter the raw number is already the whole truth, and a valuetext that
        // only repeats it would rob the reader of the percentage it works out by itself.
        aria-valuetext={format ? text : undefined}
        aria-describedby={hint ? hintId : undefined}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      {hint ? (
        <div id={hintId} className="ui-hint">
          {hint}
        </div>
      ) : null}
    </div>
  );
}
