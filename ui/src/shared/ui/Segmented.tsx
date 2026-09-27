import { useId, useRef, type KeyboardEvent, type ReactNode } from "react";

import InfoTip from "./InfoTip";

export interface SegmentedOption<T> {
  value: T;
  label: string;
}

// T is pinned to primitives; otherwise the option values would widen to string | number and the
// caller would lose the exact literal type of the setting.
export interface SegmentedProps<T extends string | number> {
  label: string;
  value: T;
  options: SegmentedOption<T>[];
  onChange: (value: T) => void;
  hint?: ReactNode;
  /** The longer explanation, behind an "i" beside the label. */
  tip?: ReactNode;
  /** Read out at the end of the label's line, as a slider shows its value. */
  aside?: ReactNode;
}

/**
 * A single choice, sized for two to four options.
 *
 * It is a radio group, not a row of buttons: the highlight alone said which option was current,
 * so a screen reader announced three unrelated buttons with no way to tell. That contract brings
 * the keyboard with it -- one tab stop for the whole group, arrows between the options, and
 * selection following focus, which is what the platform's own radio buttons do.
 *
 * The options stay <button>s carrying role="radio" rather than real <input type="radio">s: the
 * segmented look needs a styleable box, which a native radio would only get through a
 * hidden-input-and-label dance.
 */
export default function Segmented<T extends string | number>({
  label,
  value,
  options,
  onChange,
  hint = null,
  tip = null,
  aside = null,
}: SegmentedProps<T>) {
  const labelId = useId();
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  const selected = options.findIndex((o) => o.value === value);
  // A value outside the options leaves nothing checked; the first option holds the tab stop then,
  // so the group can never fall out of the tab order entirely.
  const stop = selected < 0 ? 0 : selected;

  function move(from: number, delta: number) {
    const to = (from + delta + options.length) % options.length;
    const option = options[to];
    if (!option) return;
    // The focus has to be moved by hand: a re-render only changes which button holds the tab
    // stop, and the browser leaves focus where it was.
    buttons.current[to]?.focus();
    onChange(option.value);
  }

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      // Otherwise the arrow also scrolls the panel behind the group.
      event.preventDefault();
      move(index, 1);
    } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      event.preventDefault();
      move(index, -1);
    }
  }

  return (
    <div className="ui-field">
      <div className="ui-field-head">
        <span className="ui-field-title">
          <span id={labelId} className="ui-field-label">
            {label}
          </span>
          {tip ? <InfoTip topic={label}>{tip}</InfoTip> : null}
        </span>
        {aside ? <span className="ui-field-value">{aside}</span> : null}
      </div>
      <div className="ui-seg" role="radiogroup" aria-labelledby={labelId}>
        {options.map((o, i) => (
          <button
            key={String(o.value)}
            ref={(node) => {
              buttons.current[i] = node;
            }}
            type="button"
            role="radio"
            aria-checked={o.value === value}
            tabIndex={i === stop ? 0 : -1}
            onClick={() => onChange(o.value)}
            onKeyDown={(e) => onKeyDown(e, i)}
          >
            {o.label}
          </button>
        ))}
      </div>
      {hint ? <div className="ui-hint">{hint}</div> : null}
    </div>
  );
}
