/**
 * What the window shows while there is no backend to talk to.
 *
 * Both states are real and reachable: "connecting" is the gap before the channel is up, and
 * "error" is what a user sees if they open index.html directly, or if the dev server they were
 * pointed at goes away. Neither may be a blank window.
 */

import type { ReactNode } from "react";

import type { MessageKey, TFunction } from "@/shared/i18n";
import { useT } from "@/shared/i18n";

import { useBackend } from "./BackendProvider";
import { BackendError } from "./transport";

/**
 * The catalogue keys under `common.backend` are named after the transport's error codes, so the
 * code is the lookup and there is no table to keep in step. A code this build has no message for
 * comes back from `t` as the key itself, which is not a sentence -- the error's own message is
 * shown instead, the same fallback the untranslated version used.
 */
function describe(t: TFunction, error: unknown): string {
  const raw = (error instanceof Error ? error.message : "") || String(error);
  if (!(error instanceof BackendError)) return raw;
  const key = `common.${error.code}` as MessageKey;
  const translated = t(key);
  return translated === key ? raw : translated;
}

export interface BackendGateProps {
  children: ReactNode;
  /** The plaque lives in a transparent window: an error card there would cover the game. */
  quiet?: boolean;
}

export function BackendGate({ children, quiet = false }: BackendGateProps) {
  const { status, error } = useBackend();
  const t = useT();

  if (status === "connecting") {
    if (quiet) return null;
    return (
      <div className="app">
        <div className="empty muted">{t("common.connecting")}</div>
      </div>
    );
  }

  if (status === "error") {
    if (quiet) return null;
    return (
      <div className="app">
        <div className="empty">
          <h2>{t("common.noEngine")}</h2>
          <p>{describe(t, error)}</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
