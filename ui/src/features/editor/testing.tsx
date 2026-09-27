/**
 * The editor's two contexts, stubbed for component tests: every action a spy made on first use,
 * and a state with sensible defaults the test overrides.
 */

import type { ReactNode } from "react";
import { vi, type Mock } from "vitest";

import { I18nProvider } from "@/shared/i18n";

import {
  EditorActionsContext,
  EditorStateContext,
  type EditorActions,
  type EditorState,
} from "./EditorContext";

export type Spies = Record<keyof EditorActions, Mock>;

/** Every action is a spy, made on first touch: a component uses a handful of the thirty. */
export function stubActions(overrides: Partial<EditorActions> = {}): EditorActions & Spies {
  const spies = new Map<string, Mock>();
  return new Proxy({} as EditorActions & Spies, {
    get(_target, key) {
      if (typeof key !== "string") return undefined;
      let spy = spies.get(key);
      if (!spy) {
        spy = vi.fn(overrides[key as keyof EditorActions]);
        spies.set(key, spy);
      }
      return spy;
    },
  });
}

export function stubState(patch: Partial<EditorState> = {}): EditorState {
  return {
    name: "route",
    mapId: "m1",
    maps: [],
    mapMeta: null,
    size: [100, 100],
    tilesBusy: false,
    style: { color: "#f2b544", width: 3 },
    markers: [],
    selectedId: null,
    dirty: false,
    canUndo: false,
    canRedo: false,
    objects: null,
    visibleCats: {},
    view: { mode: "dim", ahead: 3, opacity: 1 },
    ...patch,
  };
}

export function EditorWrap({
  state,
  actions,
  children,
}: {
  state: EditorState;
  actions: EditorActions;
  children: ReactNode;
}) {
  return (
    <I18nProvider initial="en">
      <EditorStateContext.Provider value={state}>
        <EditorActionsContext.Provider value={actions}>{children}</EditorActionsContext.Provider>
      </EditorStateContext.Provider>
    </I18nProvider>
  );
}
