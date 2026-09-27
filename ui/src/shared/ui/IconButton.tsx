/**
 * A button whose visible content is a glyph, and which therefore has to be named in words.
 *
 * `label` is required and not optional-with-a-default on purpose: a glyph names nothing, and
 * `title` alone is the weakest source in the accessible-name algorithm -- screen readers reach
 * for it last and several do not announce it at all. Making the prop mandatory means a new icon
 * button cannot be added without someone deciding what it is called.
 *
 * `title` defaults to `label` so the mouse tooltip and the announced name agree. Pass it
 * separately only when the tooltip says something the name should not, such as a shortcut.
 */

import type { ButtonHTMLAttributes, ReactNode } from "react";

type NativeProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "aria-label" | "children">;

export interface IconButtonProps extends NativeProps {
  /** What the button does, in the user's language. Becomes the accessible name. */
  label: string;
  /** The glyph. Hidden from assistive technology: `label` is what speaks for it. */
  icon: ReactNode;
}

export default function IconButton({ label, icon, title, type, ...rest }: IconButtonProps) {
  return (
    <button
      // Inside a form a button defaults to type="submit", which would submit on Enter.
      type={type ?? "button"}
      aria-label={label}
      title={title ?? label}
      {...rest}
    >
      <span aria-hidden="true">{icon}</span>
    </button>
  );
}
