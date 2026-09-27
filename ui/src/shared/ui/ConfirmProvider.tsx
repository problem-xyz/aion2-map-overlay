/**
 * The app's own question dialog, in place of `window.confirm`.
 *
 * The native one could not be styled, and it blocked the page's script while it was up. That
 * second part broke closing the editor: Python gives the page a second to answer a close
 * request, and a native dialog nobody had answered yet looked exactly like a page that had
 * hung, so the window closed with the question still on screen.
 *
 * A question offers Cancel and one or more answers. `useConfirm` is the common case of a single
 * answer; `useAsk` is for more, such as "Close without saving" beside "Save and close".
 *
 * Questions are queued: two asked at once are shown one after the other, never stacked.
 */

import { createContext, useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import ConfirmDialog from "./ConfirmDialog";

export interface Choice<Id extends string = string> {
  id: Id;
  label: string;
  /** Gold for the answer the question leads to; red for one that throws work away. */
  tone?: "primary" | "danger";
}

/** Resolves the id of the chosen answer, or `null` for Cancel, Escape and a click outside. */
export type Ask = <Id extends string>(
  message: string,
  choices: readonly Choice<Id>[],
) => Promise<Id | null>;

export interface AskRequest {
  id: number;
  message: string;
  choices: readonly Choice[];
  resolve: (choice: string | null) => void;
}

export const AskContext = createContext<Ask | null>(null);

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [queue, setQueue] = useState<AskRequest[]>([]);
  const pending = useRef<AskRequest[]>([]);
  const nextId = useRef(1);

  const ask = useCallback(
    <Id extends string>(message: string, choices: readonly Choice<Id>[]) =>
      new Promise<Id | null>((resolve) => {
        const request: AskRequest = {
          id: nextId.current++,
          message,
          choices,
          // The dialog only ever answers with one of the ids it was given
          resolve: resolve as (choice: string | null) => void,
        };
        pending.current = [...pending.current, request];
        setQueue(pending.current);
      }),
    [],
  );

  const answer = useCallback((choice: string | null) => {
    const [head, ...rest] = pending.current;
    if (!head) return;
    pending.current = rest;
    setQueue(rest);
    head.resolve(choice);
  }, []);

  // A page torn down with a question up answers it Cancel: nothing destructive runs unasked
  useEffect(() => {
    const open = pending;
    return () => {
      open.current.forEach((r) => r.resolve(null));
      open.current = [];
    };
  }, []);

  const current = queue[0];
  return (
    <AskContext.Provider value={ask}>
      {children}
      {current && <ConfirmDialog key={current.id} request={current} onAnswer={answer} />}
    </AskContext.Provider>
  );
}
