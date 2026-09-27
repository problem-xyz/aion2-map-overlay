import { useId, type ReactNode } from "react";

export interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  /**
   * The visible label. With one, the whole row -- label, hint and track -- is the switch, as a
   * label is to its checkbox; without, only the track is drawn, and `labelledBy` names it.
   */
  label?: ReactNode;
  /** A line under the label, announced as the switch's description rather than its name. */
  hint?: ReactNode;
  /** The id of whatever names a bare switch: most often the heading of the card it heads. */
  labelledBy?: string;
  disabled?: boolean;
  title?: string;
}

/**
 * An on/off setting: a button with role="switch", so the state is one attribute that the track
 * is painted from and a screen reader reads out. A setting says what happens when it is on; the
 * off state is the same sentence, not done.
 *
 * The name is the label alone (aria-labelledby), and the hint its description: a button's name
 * is otherwise all the text inside it, and the hint would be read as part of the label.
 */
export default function Switch({
  checked,
  onChange,
  label,
  hint,
  labelledBy,
  disabled = false,
  title,
}: SwitchProps) {
  const id = useId();
  const track = <span className="ui-switch-track" aria-hidden="true" />;
  if (label === undefined) {
    return (
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-labelledby={labelledBy}
        disabled={disabled}
        title={title}
        className="ui-switch"
        onClick={() => onChange(!checked)}
      >
        {track}
      </button>
    );
  }
  const labelId = `${id}-label`;
  const hintId = `${id}-hint`;
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-labelledby={labelId}
      aria-describedby={hint ? hintId : undefined}
      disabled={disabled}
      title={title}
      className="ui-switch-row"
      onClick={() => onChange(!checked)}
    >
      <span className="ui-switch-text">
        <span id={labelId} className="ui-switch-label">
          {label}
        </span>
        {hint ? (
          <span id={hintId} className="ui-switch-hint">
            {hint}
          </span>
        ) : null}
      </span>
      {track}
    </button>
  );
}
