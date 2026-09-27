import { useCallback } from "react";

import { useT } from "@/shared/i18n";

import { useAsk } from "./useAsk";

export interface ConfirmOptions {
  /** The confirming button's text; "OK" when left out. Name the action: "Delete route". */
  confirmLabel?: string;
  /** The confirming button in red: the answer throws work away. */
  danger?: boolean;
}

export type Confirm = (message: string, options?: ConfirmOptions) => Promise<boolean>;

/**
 * Ask the user a yes/no question in the app's own dialog. Resolves `true` only on the
 * confirming button; Cancel, Escape and a click outside all resolve `false`.
 *
 * The answer is a promise, not a boolean: the page keeps running while the question is up.
 * Whatever the caller read before asking may have changed by the time it resolves.
 */
export function useConfirm(): Confirm {
  const ask = useAsk();
  const t = useT();
  return useCallback(
    (message, { confirmLabel, danger } = {}) =>
      ask(message, [
        {
          id: "ok",
          label: confirmLabel ?? t("common.dialog.ok"),
          tone: danger ? "danger" : "primary",
        },
      ]).then((choice) => choice === "ok"),
    [ask, t],
  );
}
