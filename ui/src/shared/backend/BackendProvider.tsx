/**
 * Connects to a Python object once and shares it with the tree below.
 *
 * Parameterised because the three windows talk to two different objects: the panel and the
 * editor use `backend` with `stateChanged`/`getState`, and the plaque uses `steps` with
 * `dataChanged`/`getData`. Everything else about the connection is the same, so it is one
 * provider rather than two.
 *
 * State lives in an external store rather than component state: `stateChanged` and
 * `progressChanged` arrive several times a second, and a setState per signal would re-render
 * every consumer instead of the ones that care.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import { useLatest } from "../hooks/useLatest";

import type { QtSignal } from "./contract";
import { safeParse } from "./json";
import { createStore, type Store } from "./store";
import { BackendError, call, connectObject } from "./transport";

export type ConnectionStatus = "connecting" | "ready" | "error";

/**
 * Signals listened to from the moment the object connects, before the state getter is called,
 * and held until a component subscribes.
 *
 * Python drains the notices it raised during start-up -- a map area on an unplugged monitor, a
 * damaged settings file -- inside the first getState(). No component has mounted a listener
 * by then, and QWebChannel forwards a signal only to a page that has connected to it, so
 * without this they went to nobody. A signal the object does not have is skipped.
 */
const HELD_SIGNALS = ["notify"];

interface Held {
  signal: QtSignal;
  handler: (raw: string) => void;
  payloads: string[];
}

interface BackendContextValue<TObject = unknown, TState = unknown> {
  status: ConnectionStatus;
  error: BackendError | Error | null;
  object: TObject | null;
  store: Store<TState | null>;
  /** What a held signal carried before anyone subscribed, oldest first; stops holding it. */
  takeHeld: (name: string) => string[];
}

const BackendContext = createContext<BackendContextValue | null>(null);

export interface BackendProviderProps {
  children: ReactNode;
  /** Qt object name: "backend" or "steps". */
  object?: string;
  /** Signal that carries a fresh state payload. */
  stateSignal?: string;
  /** Slot that returns the initial state. */
  stateGetter?: string;
}

export function BackendProvider({
  children,
  object: objectName = "backend",
  stateSignal = "stateChanged",
  stateGetter = "getState",
}: BackendProviderProps) {
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const [error, setError] = useState<BackendError | Error | null>(null);
  const [object, setObject] = useState<unknown>(null);
  const storeRef = useRef<Store<unknown>>(undefined as unknown as Store<unknown>);
  if (!storeRef.current) storeRef.current = createStore<unknown>(null);
  const heldRef = useRef(new Map<string, Held>());

  const takeHeld = useCallback((name: string): string[] => {
    const held = heldRef.current.get(name);
    if (!held) return [];
    heldRef.current.delete(name);
    held.signal.disconnect(held.handler);
    return held.payloads;
  }, []);

  useEffect(() => {
    let alive = true;
    let connected: Record<string, unknown> | null = null;
    let onState: ((json: string) => void) | null = null;
    const heldSignals = heldRef.current;

    connectObject<Record<string, unknown>>(objectName)
      .then(async (obj) => {
        if (!alive) return;
        connected = obj;

        onState = (json: string) => storeRef.current.set(safeParse<unknown>(json, null));
        (obj[stateSignal] as QtSignal | undefined)?.connect(onState);

        // Before the getter, which is where the start-up notices are emitted.
        for (const name of HELD_SIGNALS) {
          const signal = obj[name] as QtSignal | undefined;
          if (!signal) continue;
          const payloads: string[] = [];
          const handler = (raw: string) => void payloads.push(raw);
          signal.connect(handler);
          heldSignals.set(name, { signal, handler, payloads });
        }

        // Through `call`, not a promise of its own: the getter is what the window waits for
        // before it shows anything, so a getter that never answers has to become the error
        // card rather than a loading gate that stays up for the rest of the session.
        if (typeof obj[stateGetter] === "function") {
          const json = await call<string>(obj, stateGetter);
          if (!alive) return;
          storeRef.current.set(safeParse<unknown>(json, null));
        }

        setObject(obj);
        setStatus("ready");
      })
      .catch((e: Error) => {
        if (!alive) return;
        setError(e);
        setStatus("error");
      });

    return () => {
      alive = false;
      if (connected && onState) {
        (connected[stateSignal] as QtSignal | undefined)?.disconnect(onState);
      }
      for (const held of heldSignals.values()) held.signal.disconnect(held.handler);
      heldSignals.clear();
    };
  }, [objectName, stateSignal, stateGetter]);

  const value = useMemo<BackendContextValue>(
    () => ({ status, error, object, store: storeRef.current, takeHeld }),
    [status, error, object, takeHeld],
  );

  return <BackendContext.Provider value={value}>{children}</BackendContext.Provider>;
}

function useBackendContext<TObject, TState>(): BackendContextValue<TObject, TState> {
  const ctx = useContext(BackendContext);
  if (!ctx) throw new Error("useBackend must be used inside a BackendProvider");
  return ctx as BackendContextValue<TObject, TState>;
}

/** The connection itself: status, error and the raw object once it is ready. */
export function useBackend<TObject = unknown>() {
  const { status, error, object } = useBackendContext<TObject, unknown>();
  return { status, error, object };
}

/**
 * Subscribe to a Qt signal for as long as the component is mounted.
 *
 * The handler goes through a ref, so a parent re-render does not tear the subscription down
 * and put it back -- payloads arriving in that gap would simply be lost.
 *
 * For a held signal (HELD_SIGNALS) the first subscriber is also handed, once, whatever arrived
 * before it mounted.
 */
export function useBackendSignal<T = string>(
  name: string,
  handler: (payload: T) => void,
  options: { parse?: boolean } = {},
) {
  const { object, status, takeHeld } = useBackendContext<Record<string, unknown>, unknown>();
  const latest = useLatest(handler);
  const parse = options.parse ?? false;

  useEffect(() => {
    if (status !== "ready" || !object) return undefined;
    const signal = object[name] as QtSignal | undefined;
    if (!signal) {
      console.warn(`backend has no signal "${name}"`);
      return undefined;
    }
    const cb = (raw: string) => {
      latest.current(parse ? safeParse<T>(raw, null as T) : (raw as unknown as T));
    };
    // Connect before taking the held payloads, not after: QWebChannel stops forwarding a signal
    // once its last handler goes, and one emitted in between would be lost.
    signal.connect(cb);
    for (const raw of takeHeld(name)) cb(raw);
    return () => signal.disconnect(cb);
  }, [object, status, name, parse, latest, takeHeld]);
}

/**
 * Read a slice of backend state.
 *
 * The selector must return a primitive or a stable reference: it runs on every store change,
 * and a fresh object each time would defeat the bail-out and re-render regardless.
 */
export function useBackendState<TState, TSlice>(
  selector: (state: TState | null) => TSlice,
): TSlice {
  const { store } = useBackendContext<unknown, TState>();
  const latest = useLatest(selector);
  return useSyncExternalStore(
    store.subscribe,
    () => latest.current(store.get()),
    () => latest.current(null),
  );
}

/** Direct access to the store, for the few places that need to patch it locally. */
export function useBackendStore<TState>(): Store<TState | null> {
  return useBackendContext<unknown, TState>().store;
}
