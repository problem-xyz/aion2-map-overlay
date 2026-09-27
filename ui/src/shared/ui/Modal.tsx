import { useEffect, useRef } from "react";
import type { KeyboardEvent, MouseEvent, ReactNode } from "react";
import { createPortal } from "react-dom";

import Icon from "./Icon";
import IconButton from "./IconButton";

// What Tab stops at inside a dialog: a radio group's unchecked options have left the tab order
const TABBABLE = 'button:not([tabindex="-1"]):not(:disabled)';

export interface ModalProps {
  /** "alertdialog" for a question that has to be answered, "dialog" for anything else. */
  role?: "dialog" | "alertdialog";
  /** The id of the element that names the dialog. */
  labelledBy: string;
  /** The name of the cross in the corner. */
  closeLabel: string;
  onClose: () => void;
  className?: string;
  children: ReactNode;
}

/**
 * A framed card over a dimmed page. Everything behind it is made inert while it is up: no focus,
 * no clicks, nothing read out. Its keys stop at the scrim, so the editor's own shortcuts --
 * Delete, Ctrl+Z, the digits -- cannot act on what is underneath.
 *
 * The cross in the corner has the focus when it opens: Enter straight away closes it rather
 * than doing something. Tab goes round the dialog's buttons and nothing else.
 */
export default function Modal({
  role = "dialog",
  labelledBy,
  closeLabel,
  onClose,
  className,
  children,
}: ModalProps) {
  const scrim = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const host = scrim.current;
    const returnTo = document.activeElement as HTMLElement | null;
    const behind = Array.from(document.body.children).filter(
      (el): el is HTMLElement => el instanceof HTMLElement && !el.contains(host) && !el.inert,
    );
    behind.forEach((el) => (el.inert = true));
    host?.querySelector<HTMLButtonElement>(".ui-modal-close")?.focus();
    return () => {
      behind.forEach((el) => (el.inert = false));
      returnTo?.focus?.();
    };
  }, []);

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    e.stopPropagation();
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    } else if (e.key === "Tab") {
      const buttons = Array.from(scrim.current?.querySelectorAll<HTMLElement>(TABBABLE) ?? []);
      const at = buttons.indexOf(document.activeElement as HTMLElement);
      const next = buttons[(at + (e.shiftKey ? -1 : 1) + buttons.length) % buttons.length];
      e.preventDefault();
      next?.focus();
    }
  };

  const onScrimDown = (e: MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) onClose();
  };

  return createPortal(
    // The scrim only catches: the keys and the outside click belong to the dialog inside it
    <div
      ref={scrim}
      role="presentation"
      className="ui-modal-scrim"
      onKeyDown={onKeyDown}
      onMouseDown={onScrimDown}
    >
      <div
        className={className ? `ui-modal ui-frame ui-orn ${className}` : "ui-modal ui-frame ui-orn"}
        role={role}
        aria-modal="true"
        aria-labelledby={labelledBy}
      >
        <IconButton
          className="ui-modal-close"
          icon={<Icon name="closeGlint" />}
          label={closeLabel}
          onClick={onClose}
        />
        {children}
      </div>
    </div>,
    document.body,
  );
}
