import { useMemo, useRef } from "react";

import { useBackendStore } from "@/shared/backend/BackendProvider";
import type { AppState, Settings } from "@/shared/backend/contract";
import { useApi } from "@/shared/backend/hooks";
import { useDebouncedCallback } from "@/shared/hooks/useDebouncedCallback";

/** How long to sit on a settings change before sending it. */
export const SETTINGS_DEBOUNCE_MS = 120;

/**
 * Change a setting: apply it locally at once, send it shortly after.
 *
 * Dragging a slider produces a change per frame. Sending each one would flood the channel and
 * make the control feel laggy, but waiting to apply it locally would make it feel broken. So
 * the local store is patched immediately and the backend call is debounced -- and flushed on
 * unmount, because a pending change that never arrives is a lost setting.
 *
 * The patch holds only what changed since the last send. Re-sending every key ever touched
 * would put old values back the moment anything else moved them -- a reset to defaults, most
 * obviously. `cancel` drops what has not been sent yet, for that same reset.
 */
export function useSettingsPatch() {
  const api = useApi();
  const store = useBackendStore<AppState>();
  const pending = useRef<Partial<Settings>>({});

  const send = useDebouncedCallback(() => {
    const patch = pending.current;
    pending.current = {};
    if (Object.keys(patch).length > 0) api?.updateSettings(patch);
  }, SETTINGS_DEBOUNCE_MS);

  return useMemo(() => {
    function change<K extends keyof Settings>(key: K, value: Settings[K]) {
      store.set((state) =>
        state ? { ...state, settings: { ...state.settings, [key]: value } } : state,
      );
      pending.current[key] = value;
      send();
    }

    change.flush = send.flush;
    change.cancel = () => {
      send.cancel();
      pending.current = {};
    };
    return change;
  }, [store, send]);
}
