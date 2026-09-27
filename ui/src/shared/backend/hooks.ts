/**
 * The hooks a page uses to talk to the backend, rather than reaching for the raw object.
 *
 * `useApi` is deliberately memoised per object: recreating the wrapper on every render would
 * make every callback that closes over it a new reference, which defeats memoisation in the
 * components below.
 */

import { useMemo } from "react";

import { createBackendApi, createStepsApi, type BackendApi, type StepsApi } from "./api";
import { useBackend } from "./BackendProvider";
import type { BackendObject, StepsObject } from "./contract";

export function useApi(): BackendApi | null {
  const { object } = useBackend<BackendObject>();
  return useMemo(() => (object ? createBackendApi(object) : null), [object]);
}

export function useStepsApi(): StepsApi | null {
  const { object } = useBackend<StepsObject>();
  return useMemo(() => (object ? createStepsApi(object) : null), [object]);
}
