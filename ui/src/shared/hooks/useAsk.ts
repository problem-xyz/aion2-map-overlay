import { useContext } from "react";

import { AskContext, type Ask } from "../ui/ConfirmProvider";

/**
 * Ask the user a question with several answers in the app's own dialog. Resolves the chosen
 * answer's id, or `null` for Cancel, Escape and a click outside. For a single answer,
 * `useConfirm` reads better.
 *
 * The answer is a promise: the page keeps running while the question is up, and whatever the
 * caller read before asking may have changed by the time it resolves.
 */
export function useAsk(): Ask {
  const ask = useContext(AskContext);
  if (!ask) throw new Error("useAsk must be used inside a ConfirmProvider");
  return ask;
}
