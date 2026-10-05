/**
 * Everything the panel and the editor need around them: the connection, the toast queue, the
 * confirmation dialog, and the signals that patch state instead of replacing it.
 *
 * `stepsChanged`, `progressChanged` and `updateChanged` exist because the full state payload is
 * expensive -- it reads every route and renders every thumbnail -- while the plaque's position
 * changes on every mouse move, progress as the player walks, and a download several times a
 * second. All three are folded into the store here, so no component has to know that the state
 * arrives on four different signals.
 */

import { useEffect, type ReactNode } from "react";

import {
  useBackendSignal,
  useBackendState,
  useBackendStore,
} from "@/shared/backend/BackendProvider";
import type {
  AppState,
  ProgressTick,
  StepsState,
  TimersState,
  UpdateState,
} from "@/shared/backend/contract";
import { useI18n } from "@/shared/i18n";
import { ConfirmProvider } from "@/shared/ui/ConfirmProvider";
import { ToastProvider } from "@/shared/ui/ToastProvider";

function StatePatches() {
  const store = useBackendStore<AppState>();

  useBackendSignal<StepsState>(
    "stepsChanged",
    (steps) => store.set((s) => (s ? { ...s, steps } : s)),
    { parse: true },
  );

  useBackendSignal<ProgressTick>(
    "progressChanged",
    (tick) =>
      store.set((s) =>
        s ? { ...s, progress: { ...s.progress, done: tick.done, total: tick.total } } : s,
      ),
    { parse: true },
  );

  // Every updater change, download progress included; stateChanged follows only a new phase.
  useBackendSignal<UpdateState>(
    "updateChanged",
    (update) => store.set((s) => (s ? { ...s, update } : s)),
    { parse: true },
  );

  // The timers, when what they say changes; the whole state is never resent for them.
  useBackendSignal<TimersState | null>(
    "timersChanged",
    (timers) => store.set((s) => (s ? { ...s, timers } : s)),
    { parse: true },
  );

  return null;
}

/**
 * The language setting reaches the provider here rather than at the root, because the root
 * mounts above the backend and there is no state to read yet. Until the first state arrives the
 * UI follows the browser, which is the same answer in the overwhelmingly common case.
 */
function LanguageSync() {
  const setting = useBackendState<AppState | null, string | undefined>((s) => s?.settings.language);
  const { setLanguage } = useI18n();
  useEffect(() => {
    if (setting) setLanguage(setting);
  }, [setting, setLanguage]);
  return null;
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <ConfirmProvider>
        <LanguageSync />
        <StatePatches />
        {children}
      </ConfirmProvider>
    </ToastProvider>
  );
}
